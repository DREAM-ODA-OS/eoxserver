#-------------------------------------------------------------------------------
# $Id$
#
# Project: EOxServer <http://eoxserver.org>
# Authors: Fabian Schindler <fabian.schindler@eox.at>
#
#-------------------------------------------------------------------------------
# Copyright (C) 2013 EOX IT Services GmbH
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies of this Software or works derived from this Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#-------------------------------------------------------------------------------


from os import remove
from os.path import splitext, abspath, join, exists, isfile
from datetime import datetime
from uuid import uuid4
import logging
from subprocess import call

from django.contrib.gis.geos import GEOSGeometry

from eoxserver.core import Component, implements
from eoxserver.core.config import get_eoxserver_config
from eoxserver.core.decoders import config
from eoxserver.core.util.rect import Rect
from eoxserver.backends.access import connect
from eoxserver.contrib import gdal, osr
from eoxserver.contrib.vrt import VRTBuilder
from eoxserver.resources.coverages import models
from eoxserver.services.ows.version import Version
from eoxserver.services.result import ResultFile, ResultBuffer
from eoxserver.services.ows.wcs.interfaces import WCSCoverageRendererInterface
from eoxserver.services.ows.wcs.v20.encoders import WCS20EOXMLEncoder
from eoxserver.services.exceptions import (
    RenderException, OperationNotSupportedException
)
from eoxserver.processing.gdal import reftools
from eoxserver.resources.coverages.formats import getFormatRegistry


logger = logging.getLogger(__name__)

class WCSConfigReader(config.Reader):
    section = "services.ows.wcs"
    maxsize = config.Option(type=int, default=None)

class SystemConfigReader(config.Reader):
    section = "core.system"
    path_temp = config.Option(type=str, default=None)
    path_beam = config.Option(type=str, default=None)
    beam_options = config.Option(type=str, default='')


class GDALReferenceableDatasetRenderer(Component):
    implements(WCSCoverageRendererInterface)

    versions = (Version(2, 0),)

    def supports(self, params):
        return (
            issubclass(params.coverage.real_type, models.ReferenceableDataset)
            and params.version in self.versions
        )


    def render(self, params):
        # get the requested coverage, data items and range type.
        coverage = params.coverage
        data_items = coverage.data_items.filter(semantic__startswith="bands")
        range_type = coverage.range_type

        subsets = params.subsets

        # GDAL source dataset. Either a single file dataset or a composed VRT
        # dataset.
        src_ds = self.get_source_dataset(
            coverage, data_items, range_type
        )

        # retrieve area of interest of the source image according to given
        # subsets
        src_rect, dst_rect = self.get_src_and_dst_rect(src_ds, subsets)

        # deduct "native" format of the source image
        def _src2nat(src_format):
            if src_format is not None:
                frmreg = getFormatRegistry()
                f_src = frmreg.getFormatByMIME(src_format)
                f_dst = frmreg.mapSourceToNativeWCS20(f_src)
                if f_dst is not None:
                    return f_dst.mimeType
            return None

        source_format = data_items[0].format if len(data_items) == 1 else None
        native_format = _src2nat(source_format)

        # get the requested image format, which defaults to the native format
        # if available
        output_format = params.format or native_format

        if not output_format:
            raise RenderException("Failed to deduce the native format of "
                "the coverage. Output format must be provided!", "format")

        if params.scalefactor is not None or params.scales:
            raise RenderException(
                "ReferenceableDataset cannot be scaled.",
                "scalefactor" if params.scalefactor is not None else "scale"
            )

        # check it the requested image fits the max. allowed coverage size
        maxsize = WCSConfigReader(get_eoxserver_config()).maxsize
        if maxsize < dst_rect.size_x or maxsize < dst_rect.size_y:
            raise RenderException(
                "Requested image size %dpx x %dpx exceeds the allowed "
                "limit maxsize=%dpx!" % (dst_rect.size_x,
                dst_rect.size_y, maxsize), "size"
            )

        # get the output backend and driver for the requested format
        def _get_driver(mime_src, mime_out):
            """Select backend for the given source and output formats."""
            # TODO: make this configurable
            if mime_src == 'application/x-esa-envisat' and \
               mime_out == 'application/x-netcdf':
                return "BEAM", "NetCDF-CF"

            frmreg = getFormatRegistry()
            fobj = frmreg.getFormatByMIME(mime_out)
            backend, _, driver = fobj.driver.partition("/")
            return backend, driver

        driver_backend, driver_name = _get_driver(source_format, output_format)

        if driver_backend not in ("GDAL", "BEAM"):
            raise RenderException("Invallid output format backend name %s!"
                                  "" % driver_backend, "format")

        # prepare output
        # ---------------------------------------------------------------------
        if driver_backend == "BEAM":

            path_out, extension = self.encode_beam(
                driver_name,
                src_ds.GetFileList()[0],
                src_rect,
                getattr(params, "encoding_params", {})
            )

            mime_type = output_format
            path_list = [path_out]

        # ---------------------------------------------------------------------
        elif driver_backend == "GDAL":

            # get the output driver
            driver = gdal.GetDriverByName(driver_name)
            if driver is None:
                raise RenderException("Unsupported GDAL driver %s!" % driver_name)

            # perform subsetting either with or without rangesubsetting
            subsetted_ds = self.get_subset(
                src_ds, range_type, src_rect, dst_rect, params.rangesubset
            )

            # encode the processed dataset and save it to the filesystem
            out_ds = self.encode(driver, subsetted_ds, output_format,
                        getattr(params, "encoding_params", {}))

            driver_metadata = driver.GetMetadata_Dict()
            mime_type = driver_metadata.get("DMD_MIMETYPE")
            extension = driver_metadata.get("DMD_EXTENSION")
            path_list = out_ds.GetFileList()

        # ---------------------------------------------------------------------

        time_stamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename_base = "%s_%s" % (coverage.identifier, time_stamp)

        result_set = [
            ResultFile(
                path_item, mime_type, "%s.%s" % (filename_base, extension),
                ("cid:coverage/%s" % coverage.identifier) if i == 0 else None
            ) for i, path_item in enumerate(path_list)
        ]

        if params.mediatype and params.mediatype.startswith("multipart"):
            reference = "cid:coverage/%s" % result_set[0].filename

            if subsets.has_x and subsets.has_y:
                footprint = GEOSGeometry(reftools.get_footprint_wkt(out_ds))
                if not subsets.srid:
                    extent = footprint.extent
                else:
                    extent = subsets.xy_bbox
                encoder_subset = (
                    subsets.srid, src_rect.size, extent, footprint
                )
            else:
                encoder_subset = None

            encoder = WCS20EOXMLEncoder()
            content = encoder.serialize(
                encoder.encode_referenceable_dataset(
                    coverage, range_type, reference, mime_type, encoder_subset
                )
            )
            result_set.insert(0, ResultBuffer(content, encoder.content_type))

        return result_set


    def get_source_dataset(self, coverage, data_items, range_type):
        if len(data_items) == 1:
            return gdal.OpenShared(abspath(connect(data_items[0])))
        else:
            vrt = VRTBuilder(
                coverage.size_x, coverage.size_y,
                vrt_filename=temp_vsimem_filename()
            )

            # sort in ascending order according to semantic
            data_items = sorted(data_items, key=(lambda d: d.semantic))

            gcps = []
            compound_index = 0
            for data_item in data_items:
                path = abspath(connect(data_item))

                # iterate over all bands of the data item
                for set_index, item_index in self._data_item_band_indices(data_item):
                    if set_index != compound_index + 1:
                        raise ValueError
                    compound_index = set_index

                    band = range_type[set_index]
                    vrt.add_band(band.data_type)
                    vrt.add_simple_source(
                        set_index, path, item_index
                    )

            return vrt.dataset


    @staticmethod
    def get_src_and_dst_rect(dataset, subsets):
        """ Get extent (pixel rectangle) of the source and destination
        images matching the requested subsetting.
        """
        size_x, size_y = dataset.RasterXSize, dataset.RasterYSize
        image_rect = Rect(0, 0, size_x, size_y)

        if not subsets:
            subset_rect = image_rect

        # pixel subset
        elif subsets.srid is None: # means "imageCRS"
            minx, miny, maxx, maxy = subsets.xy_bbox

            minx = int(minx) if minx is not None else image_rect.offset_x
            miny = int(miny) if miny is not None else image_rect.offset_y
            maxx = int(maxx) if maxx is not None else image_rect.upper_x
            maxy = int(maxy) if maxy is not None else image_rect.upper_y

            subset_rect = Rect(minx, miny, maxx-minx+1, maxy-miny+1)

        # subset in geographical coordinates
        else:
            vrt = VRTBuilder(*image_rect.size)
            vrt.copy_gcps(dataset)

            options = reftools.suggest_transformer(dataset)

            subset_rect = reftools.rect_from_subset(
                vrt.dataset, subsets.srid, *subsets.xy_bbox, **options
            )

        # check whether or not the subsets intersect with the image
        if not image_rect.intersects(subset_rect):
            raise RenderException("Subset outside coverage extent.", "subset")

        src_rect = subset_rect & image_rect
        dst_rect = src_rect - src_rect.offset

        return src_rect, dst_rect


    @staticmethod
    def get_subset(src_ds, range_type, subset_rect, dst_rect, rangesubset=None):
        """ Get subset of the image (as GDAL dataset) matching the requsted
            pixel rectangle.
        """
        vrt = VRTBuilder(*subset_rect.size)

        input_bands = list(range_type)

        # list of band indices/names. defaults to all bands
        if rangesubset:
            subset_bands = rangesubset.get_band_indices(range_type, 1)
        else:
            subset_bands = xrange(1, len(range_type) + 1)

        for dst_index, src_index in enumerate(subset_bands, start=1):
            input_band = input_bands[src_index-1]
            vrt.add_band(input_band.data_type)
            vrt.add_simple_source(
                dst_index, src_ds, src_index, subset_rect, dst_rect
            )

        vrt.copy_metadata(src_ds)
        vrt.copy_gcps(src_ds, subset_rect)

        return vrt.dataset


    @staticmethod
    def encode(driver, dataset, mime_type, encoding_params):
        """ Encode (i.e., create) the output image and return the opened GDAL
        dataset object.
        """

        # temporary filename
        path_temp = SystemConfigReader(get_eoxserver_config()).path_temp
        while True:
            path = join(path_temp, "eoxs_tmp_%s" % uuid4().hex)
            if not exists(path):
                break

        # parse the encoding options
        options = ()
        if mime_type == "image/tiff":
            options = _get_gtiff_options(**encoding_params)

        args = [("%s=%s" % key, value) for key, value in options]
        return driver.CreateCopy(path, dataset, True, args)


    @staticmethod
    def encode_beam(driver_name, path_src, src_rect, encoding_params):

        # get and check the location of the BEAM toolbox
        sys_config = SystemConfigReader(get_eoxserver_config())
        path_beam = sys_config.path_beam
        beam_options = [f for f in sys_config.beam_options.split()]

        if path_beam is None:
            raise RenderException("Path to BEAM toolbox is not defined!", "config")

        path_beam_gpt = join(path_beam, 'bin/gpt.sh')
        if not isfile(path_beam_gpt):
            raise RenderException("Invalid path to BEAM toolbox %s!" % repr(path_beam), "config")

        # mime-type and output extenstion
        if driver_name.startswith("NetCDF-"):
            extension = ".nc"
        elif driver_name.startswith("NetCDF4-"):
            extension = ".nc4"
        elif driver_name.startswith("GeoTIFF"):
            extension = ".tif"
        else:
            extension = ""

        # temporary filename
        path_temp = SystemConfigReader(get_eoxserver_config()).path_temp
        while True:
            path_base = join(path_temp, "eoxs_tmp_%s" % uuid4().hex)
            path_gpt = "%s%s"%(path_base, ".gpt")
            path_data = "%s%s"%(path_base, extension)
            if not exists(path_gpt) and not exists(path_data):
                break

        # BEAM graph generator
        def _graph():
            yield '<graph id="data_subset">'
            yield '  <version>1.0</version> '
            yield '  <node id="subsetter">'
            yield '    <operator>Subset</operator>'
            yield '    <sources>'
            yield '      <sourceProduct>${INPUT}</sourceProduct>'
            yield '    </sources>'
            yield '    <parameters>'
            yield '      <region>'
            yield '        <x>%d</x>' % src_rect.offset_x
            yield '        <y>%d</y>' % src_rect.offset_y
            yield '        <width>%d</width>' % src_rect.size_x
            yield '        <height>%d</height>' % src_rect.size_y
            yield '      </region>'
            yield '    </parameters>'
            yield '  </node>'
            yield '  <node id="writer">'
            yield '    <operator>Write</operator>'
            yield '    <sources>'
            yield '      <source>subsetter</source>'
            yield '    </sources>'
            yield '    <parameters>'
            yield '      <file>${OUTPUT}</file>'
            yield '      <formatName>%s</formatName>' % driver_name
            yield '      <deleteOutputOnFailure>true</deleteOutputOnFailure>'
            yield '      <writeEntireTileRows>false</writeEntireTileRows>'
            yield '      <clearCacheAfterRowWrite>true</clearCacheAfterRowWrite>'
            yield '    </parameters>'
            yield '  </node>'
            yield '</graph>'

        try:
            with file(path_gpt, "w") as fid:
                for item in _graph():
                    logger.debug(item)
                    fid.write(item)

            beam_gpt_argv = [
                    path_beam_gpt,
                    path_gpt,
                    '-SINPUT=%s' % path_src,
                    '-POUTPUT=%s' % path_data
                  ] + beam_options

            logger.debug("%s", beam_gpt_argv)

            if call(beam_gpt_argv):
                raise RenderException("BEAM toolbox failed to generate the output!", "beam")

        except:
            if isfile(path_data):
                remove(path_data)
            raise

        finally:
            if isfile(path_gpt):
                remove(path_gpt)

        return path_data, extension


def index_of(iterable, predicate, default=None, start=1):
    for i, item in enumerate(iterable, start):
        if predicate(item):
            return i
    return default


def temp_vsimem_filename():
    return "/vsimem/%s" % uuid4().hex


def _get_gtiff_options(compression=None, jpeg_quality=None,
                       predictor=None, interleave=None, tiling=False,
                       tilewidth=None, tileheight=None):

    logger.info("Applying GeoTIFF parameters.")

    if compression:
        if compression.lower() == "huffman":
            compression = "CCITTRLE"
        yield ("COMPRESS", compression.upper())

    if jpeg_quality is not None:
        yield ("JPEG_QUALITY", str(jpeg_quality))

    if predictor:
        pr = ["NONE", "HORIZONTAL", "FLOATINGPOINT"].index(predictor.upper())
        if pr == -1:
            raise ValueError("Invalid compression predictor '%s'." % predictor)
        yield ("PREDICTOR", str(pr + 1))

    if interleave:
        yield ("INTERLEAVE", interleave)

    if tiling:
        yield ("TILED", "YES")
        if tilewidth is not None:
            yield ("BLOCKXSIZE", str(tilewidth))
        if tileheight is not None:
            yield ("BLOCKYSIZE", str(tileheight))


