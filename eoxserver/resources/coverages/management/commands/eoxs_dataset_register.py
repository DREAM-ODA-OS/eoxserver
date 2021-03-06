#-------------------------------------------------------------------------------
# $Id$
#
# Project: EOxServer <http://eoxserver.org>
# Authors: Fabian Schindler <fabian.schindler@eox.at>
#          Martin Paces <martin.paces@eox.at>
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

from lxml import etree
from optparse import make_option
#from itertools import chain

#from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError, BaseCommand
from django.utils.dateparse import parse_datetime
from django.contrib.gis import geos 

from eoxserver.core import env
from eoxserver.contrib import gdal, osr, ogr
from eoxserver.backends import models as backends
from eoxserver.backends.component import BackendComponent
from eoxserver.backends.cache import CacheContext
from eoxserver.backends.access import connect
from eoxserver.resources.coverages import models
from eoxserver.resources.coverages.metadata.component import MetadataComponent
from eoxserver.resources.coverages.management.commands import (
    CommandOutputMixIn, _variable_args_cb, nested_commit_on_success
)

# common spatial reference object
SR_WGS84 = osr.SpatialReference(4326).sr

def _variable_args_cb_list(option, opt_str, value, parser):
    """ Helper function for optparse module. Allows variable number of option 
        values when used as a callback.
    """
    args = []
    for arg in parser.rargs:
        if not arg.startswith('-'):
            args.append(arg)
        else:
            del parser.rargs[:len(args)]
            break
    if not getattr(parser.values, option.dest):
        setattr(parser.values, option.dest, [])

    getattr(parser.values, option.dest).append(args)


class Command(CommandOutputMixIn, BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option("-i", "--identifier", "--coverage-id", dest="identifier",
            action="store", default=None,
            help=("Override identifier.")
        ),
        make_option("-d", "--data", dest="data",
            action="callback", callback=_variable_args_cb_list, default=[],
            help=("Add a data item to the dataset. Format is: "
                  "[storage_type:url] [package_type:location]* format:location"
                 )
        ),
        make_option("-s", "--semantic", dest="semantics",
            action="callback", callback=_variable_args_cb, default=None,
            help=("Optional band semantics. If given, one band "
                  "semantics 'band[*]' must be present for each '--data' "
                  "option.")
        ),
        make_option("-m", "--meta-data", dest="metadata", 
            action="callback", callback=_variable_args_cb_list, default=[],
            help=("Optional. [storage_type:url] [package_type:location]* "
                  "format:location")
        ),
        make_option("-r", "--range-type", dest="range_type_name",
            help=("Mandatory. Name of the stored range type. ")
        ),

        make_option("-e", "--extent", dest="extent", 
            action="store", default=None,
            help=("Override extent. Comma separated list of "
                  "<minx>,<miny>,<maxx>,<maxy>.")
        ),

        make_option("--size", dest="size", 
            action="store", default=None,
            help=("Override size. Comma separated list of <size-x>,<size-y>.")
        ),

        make_option("--srid", dest="srid", 
            action="store", default=None,
            help=("Override SRID. Integer number.")
        ),

        make_option("-p", "--projection", dest="projection", 
            action="store", default=None,
            help=("Override projection.")
        ),

        make_option("-f", "--footprint", dest="footprint", 
            action="store", default=None,
            help=("Override footprint. Must be supplied as WKT Polygons or "
                  "MultiPolygons.")
        ),

        make_option("--begin-time", dest="begin_time", 
            action="store", default=None,
            help=("Override begin time. Format is ISO8601 datetime strings.")
        ),

        make_option("--end-time", dest="end_time", 
            action="store", default=None,
            help=("Override end time. Format is ISO8601 datetime strings.")
        ),

        make_option("--coverage-type", dest="coverage_type",
            action="store", default=None,
            help=("The actual coverage type.")
        ),

        make_option("--visible", dest="visible",
            action="store_true", default=False,
            help=("Set the coverage to be 'visible', which means it is "
                  "advertised in GetCapabilities responses.")
        ),

        make_option("--collection", dest="collection_ids",
            action='callback', callback=_variable_args_cb, default=None, 
            help=("Optional. Link to one or more collection(s).")
        ), 

        make_option('--ignore-missing-collection', 
            dest='ignore_missing_collection', 
            action="store_true", default=False,
            help=("Optional. Proceed even if the linked collection "
                  "does not exist. By defualt, a missing collection " 
                  "will result in an error.")
        ),

        make_option("--cloud", dest="pm_cloud",
            action="store", default=None,
            help=("Optional cloud polygon mask.")
        ),

        make_option("--snow", dest="pm_snow",
            action="store", default=None,
            help=("Optional snow polygon mask.")
        ),

        make_option("--view", dest="md_wms_view",
            action="store", default=None,
            help=("Optional link WMS view to another EO-ID (layer).")
        ),

        make_option("--alias", dest="md_wms_alias",
            action="store", default=None,
            help=("Optional EO-ID (layer) of another dataset"
                  "the registered coverage provides view to.")
        ),
    )

    args = (
        "-d [<storage>:][<package>:]<location> [-d ... ] "
        "-r <range-type-name> "
        "[-m [<storage>:][<package>:]<location> [-m ... ]] "
        "[-s <semantic> [-s <semantic>]] "
        "[--identifier <identifier>] "
        "[-e <minx>,<miny>,<maxx>,<maxy>] "
        "[--size <size-x> <size-y>] "
        "[--srid <srid> | --projection <projection-def>] "
        "[--footprint <footprint-wkt>] "
        "[--begin-time <begin-time>] [--end-time <end-time>] "
        "[--coverage-type <coverage-type-name>] "
        "[--visible] [--collection <collection-id> [--collection ... ]] "
        "[--ignore-missing-collection]"
    )

    help = """
        Registers a Dataset.
        A dataset is a collection of data and metadata items. When beeing 
        registered, as much metadata as possible is extracted from the supplied
        (meta-)data items. If some metadata is still missing, it needs to be 
        supplied via the specific override options.

        By default, datasets are not "visible" which means that they are not 
        advertised in the GetCapabilities sections of the various services.
        This needs to be overruled via the `--visible` switch.

        The registered dataset can optionally be directly inserted one or more
        collections.
    """

    @nested_commit_on_success
    def handle(self, *args, **kwargs):
        with CacheContext() as cache:
            self.handle_with_cache(cache, *args, **kwargs)


    def handle_with_cache(self, cache, *args, **kwargs):
        metadata_component = MetadataComponent(env)
        datas = kwargs["data"]
        semantics = kwargs.get("semantics")
        metadatas = kwargs["metadata"]
        range_type_name = kwargs["range_type_name"]
        polygon_mask_cloud = kwargs["pm_cloud"]
        polygon_mask_snow = kwargs["pm_snow"]
        wms_view = kwargs["md_wms_view"]
        wms_alias = kwargs["md_wms_alias"]

        if range_type_name is None:
            raise CommandError("No range type name specified.")
        range_type = models.RangeType.objects.get(name=range_type_name)

        metadata_keys = set((
            "identifier", "extent", "size", "projection",
            "footprint", "begin_time", "end_time", "coverage_type",
        ))

        all_data_items = []
        retrieved_metadata = {}

        retrieved_metadata.update(
            self._get_overrides(**kwargs)
        )

        #----------------------------------------------------------------------
        # meta-data

        vector_masks_src = []

        for metadata in metadatas:
            storage, package, format, location = self._get_location_chain(
                metadata
            )
            data_item = backends.DataItem(
                location=location, format=format or "", semantic="metadata", 
                storage=storage, package=package,
            )
            data_item.full_clean()
            data_item.save()
            all_data_items.append(data_item)

            with open(connect(data_item, cache)) as f:
                content = etree.parse(f)
                reader = metadata_component.get_reader_by_test(content)
                if reader:
                    values = reader.read(content)

                    format = values.pop("format", None)
                    if format:
                        data_item.format = format
                        data_item.full_clean()
                        data_item.save()

                    for key, value in values.items():
                        if key in metadata_keys:
                            retrieved_metadata.setdefault(key, value)

                    vector_masks_src = values.get("vmasks", [])

        #----------------------------------------------------------------------
        # polygon masks

        def _get_geometry(file_name):
            """ load geometry from a feature collection """
            # TODO: improve the feature selection
            ds = ogr.Open(file_name)
            ly = ds.GetLayer(0)
            ft = ly.GetFeature(0)
            g0 = ft.GetGeometryRef()
            g0.TransformTo(SR_WGS84) # geometries always stored in WGS84
            return geos.GEOSGeometry(buffer(g0.ExportToWkb()), srid=4326)

        if polygon_mask_cloud is not None:
            vector_masks_src.append({
                    'type': 'CLOUD',
                    'subtype': None,
                    'mask': _get_geometry(polygon_mask_cloud),
                })

        if polygon_mask_snow is not None:
            vector_masks_src.append({
                    'type': 'SNOW',
                    'subtype': None,
                    'mask': _get_geometry(polygon_mask_snow),
                })

        #----------------------------------------------------------------------
        # handle vector masks

        vector_masks = []
        VMASK_TYPE = dict((v, k) for (k, v) in models.VectorMask.TYPE_CHOICES)

        for vm_src in vector_masks_src:
            if vm_src["type"] not in VMASK_TYPE:
                raise CommandError("Invalid mask type '%s'! Allowed "
                    "mask-types are: %s", vm_src["type"],
                        "|".join(VMASK_TYPE.keys()))

            vm = models.VectorMask()
            vm.type = VMASK_TYPE[vm_src["type"]]
            vm.subtype = vm_src["subtype"]
            vm.geometry = vm_src["mask"]

            #TODO: improve the semantic handling 
            if vm.subtype:
                vm.semantic = ("%s_%s"%(vm_src["type"],
                                vm_src["subtype"].replace(" ", "_"))).lower()
            else:
                vm.semantic = vm_src["type"].lower()

            vector_masks.append(vm)

        #----------------------------------------------------------------------
        # meta-data

        metadata_items = []

        # prerendered WMS view
        if wms_view is not None:
            metadata_items.append(
                models.MetadataItem(semantic="wms_view", value=wms_view)
            )

        # alias of the WMS view
        if wms_alias is not None:
            metadata_items.append(
                models.MetadataItem(semantic="wms_alias", value=wms_alias)
            )

        #----------------------------------------------------------------------
        # coverage 

        if len(datas) < 1:
            raise CommandError("No data files specified.")

        if semantics is None:
            # TODO: check corner cases.
            # e.g: only one data item given but multiple bands in range type
            # --> bands[1:<bandnum>]
            if len(datas) == 1:
                if len(range_type) == 1:
                    semantics = ["bands[1]"]
                else:
                    semantics = ["bands[1:%d]" % len(range_type)]
            
            else:
                semantics = ["bands[%d]" % i for i in range(len(datas))]


        for data, semantic in zip(datas, semantics):
            storage, package, format, location = self._get_location_chain(data)
            data_item = backends.DataItem(
                location=location, format=format or "", semantic=semantic, 
                storage=storage, package=package,
            )
            data_item.full_clean()
            data_item.save()
            all_data_items.append(data_item)

            # TODO: other opening methods than GDAL
            ds = gdal.Open(connect(data_item, cache))
            reader = metadata_component.get_reader_by_test(ds)
            if reader:
                values = reader.read(ds)

                format = values.pop("format", None)
                if format:
                    data_item.format = format
                    data_item.full_clean()
                    data_item.save()

                for key, value in values.items():
                    if key in metadata_keys:
                        retrieved_metadata.setdefault(key, value)
            ds = None

        if len(metadata_keys - set(retrieved_metadata.keys())):
            raise CommandError(
                "Missing metadata keys %s." 
                % ", ".join(metadata_keys - set(retrieved_metadata.keys()))
            )

        try:
            # TODO: allow types of different apps
            CoverageType = getattr(models, retrieved_metadata["coverage_type"])
        except AttributeError:
            raise CommandError(
                "Type '%s' is not supported." % kwargs["coverage_type"]
            )

        try:
            coverage = CoverageType()
            coverage.range_type = range_type
            
            proj = retrieved_metadata.pop("projection")
            if isinstance(proj, int):
                retrieved_metadata["srid"] = proj
            else:
                definition, format = proj

                # Try to identify the SRID from the given input
                try:
                    sr = osr.SpatialReference(definition, format)
                    retrieved_metadata["srid"] = sr.srid
                except Exception, e:
                    prj = models.Projection.objects.get(
                        format=format, definition=definition
                    )
                    retrieved_metadata["projection"] = prj

            # TODO: bug in models for some coverages
            for key, value in retrieved_metadata.items():
                setattr(coverage, key, value)

            coverage.visible = kwargs["visible"]

            coverage.full_clean()
            coverage.save()

            for data_item in all_data_items:
                data_item.dataset = coverage
                data_item.full_clean()
                data_item.save()

            for vm in vector_masks:
                vm.coverage = coverage 
                vm.full_clean()
                vm.save()

            for md in metadata_items:
                md.eo_object = coverage
                md.full_clean()
                md.save()

            # link with collection(s)
            if kwargs["collection_ids"]:
                ignore_missing_collection = kwargs["ignore_missing_collection"]
                call_command("eoxs_collection_link",
                    collection_ids=kwargs["collection_ids"], 
                    add_ids=[coverage.identifier],
                    ignore_missing_collection=ignore_missing_collection
                )

        except Exception as e: 
            self.print_traceback(e, kwargs)
            raise CommandError("Dataset registration failed: %s" % e)

        self.print_msg(
            "Dataset with ID '%s' registered sucessfully." 
            % coverage.identifier
        ) 

        
    def _get_overrides(self, identifier=None, size=None, extent=None, 
                       begin_time=None, end_time=None, footprint=None, 
                       projection=None, srid=None, coverage_type=None, **kwargs):

        overrides = {}

        if coverage_type:
            overrides["coverage_type"] = coverage_type

        if identifier:
            overrides["identifier"] = identifier

        if extent:
            overrides["extent"] = map(float, extent.split(","))

        if size:
            overrides["size"] = map(int, size.split(","))            

        if begin_time:
            overrides["begin_time"] = parse_datetime(begin_time)

        if end_time:
            overrides["end_time"] = parse_datetime(end_time)

        if footprint:
            footprint = geos.GEOSGeometry(footprint)
            if footprint.hasz :
                raise CommandError(
                    "Invalid footprint geometry! 3D geometry is not supported!"
                )
            if footprint.geom_type == "MultiPolygon" :
                overrides["footprint"] = footprint
            elif footprint.geom_type == "Polygon" :
                overrides["footprint"] = geos.MultiPolygon(footprint)
            else : 
                raise CommandError(
                    "Invalid footprint geometry type '%s'!"
                    % (footprint.geom_type)
                )

        if projection:
            try:
                overrides["projection"] = int(projection)
            except ValueError:
                overrides["projection"] = projection

        if srid:
            overrides["projection"] = int(srid)

        return overrides


    def _get_location_chain(self, items):
        """ Returns the tuple
        """
        component = BackendComponent(env)
        storage = None
        package = None

        storage_type, url = self._split_location(items[0])
        if storage_type:
            storage_component = component.get_storage_component(storage_type)
        else:
            storage_component = None

        if storage_component:
            storage, _ = backends.Storage.objects.get_or_create(
                url=url, storage_type=storage_type
            )

        # packages
        for item in items[1 if storage else 0:-1]:
            type_or_format, location = self._split_location(item)
            package_component = component.get_package_component(type_or_format)
            if package_component:
                package, _ = backends.Package.objects.get_or_create(
                    location=location, format=format, 
                    storage=storage, package=package
                )
                storage = None # override here
            else:
                raise Exception(
                    "Could not find package component for format '%s'"
                    % type_or_format
                )

        format, location = self._split_location(items[-1])
        return storage, package, format, location


    def _split_location(self, item):
        """ Splits string as follows: <format>:<location> where format can be 
            None.
        """
        p = item.find(":")
        if p == -1:
            return None, item 
        return item[:p], item[p + 1:]


def save(model):
    model.full_clean()
    model.save()
    return model
