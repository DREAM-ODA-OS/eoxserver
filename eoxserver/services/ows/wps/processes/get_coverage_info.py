#-------------------------------------------------------------------------------
#
# Project: EOxServer <http://eoxserver.org>
# Authors: Martin Paces <martin.paces@eox.at>
#
#-------------------------------------------------------------------------------
# Copyright (C) 2014 EOX IT Services GmbH
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

from datetime import datetime

from django.contrib.gis.geos import Point
from django.contrib.gis.gdal import SpatialReference
from eoxserver.core.config import get_eoxserver_config
from eoxserver.core import Component, implements
from eoxserver.core.util.timetools import isoformat

from eoxserver.services.ows.wps.interfaces import ProcessInterface
from eoxserver.services.ows.wps.parameters import (
    LiteralData, ComplexData, CDTextBuffer, CDAsciiTextBuffer, FormatText,
    AllowedRange,
)
from eoxserver.services.ows.wps.exceptions import (
    ExecuteError, InvalidInputValueError,
)

from eoxserver.resources.coverages.models import DatasetSeries, Coverage

# get the service URL
URL = get_eoxserver_config().get("services.owscommon", "http_service_url")

class GetCoverageInfoProcess(Component):
    """ Get information about the top-most visible coverage.
    """

    implements(ProcessInterface)

    identifier = "getCoverageInfo"
    title = "Get Coverage Information"
    metadata = {}
    profiles = ['EOxServer:GetCoverageInfo']

    inputs = (
        ("collection", LiteralData("collection", str,
            title="Collection name (a.k.a. dataset-series identifier).")),
        ("begin_time", LiteralData("begin_time", datetime, optional=True,
            title="Optional start of the time interval.")),
        ("end_time", LiteralData("end_time", datetime, optional=True,
            title="Optional end of the time interval.")),
        ("latitude", LiteralData("latitude", float,
            title="Point of interest - latitude.",
            allowed_values=AllowedRange(-90.0, +90.0, dtype=float),
            uoms=(('dg', 1.0),))),
        ("longitude", LiteralData("longitude", float,
            title="Point of interest - longitude.",
            allowed_values=AllowedRange(-180.0, +180.0, dtype=float),
            uoms=(('dg', 1.0),))),
    )

    outputs = (
        ("info", ComplexData("info", formats=FormatText('text/html'),
                    title="Coverage information in HTML format.")),
    )

    @classmethod
    def execute(cls, collection, begin_time, end_time, latitude, longitude, **kwarg):
        """ The main execution function for the process.
        """

        # point of ineterest
        point = Point(longitude, latitude, srid=4326)

        # get the dataset series matching the requested ID
        try:
            series = DatasetSeries.objects.get(identifier=collection)
        except DatasetSeries.DoesNotExist:
            raise InvalidInputValueError("collection", "Invalid collection name '%s'!"%collection)

        # recursive nested collection lookup
        def _get_children_ids(ds):
            ds_rct = ds.real_content_type
            id_list = [ds.id]
            for child in series.eo_objects.filter(real_content_type=ds_rct):
                id_list.extend(_get_children_ids(child))
            return id_list

        # prepare coverage query set
        coverages_qs = Coverage.objects.filter(
                                 collections__id__in=_get_children_ids(series))
        if end_time is not None:
            coverages_qs = coverages_qs.filter(begin_time__lte=end_time)
        if begin_time is not None:
            coverages_qs = coverages_qs.filter(end_time__gte=begin_time)
        coverages_qs = coverages_qs.filter(footprint__contains=point)
        coverages_qs = coverages_qs.order_by('-begin_time', '-end_time', '-identifier')

        # create the output
        output = CDAsciiTextBuffer()

        try:
            coverage = coverages_qs[:1].get()
        except Coverage.DoesNotExist:
            return output
            #raise ExecuteError("No coverage matching the input parameters"
            #                   " found.", "%s.execute()"%cls.identifier)

        for s in cls.cov2html(coverage):
            output.write(s)

        return output

    @classmethod
    def cov2html(cls, coverage):
        """ generate html info """
        def _get_browse_url(coverage):
            ext = coverage.footprint.extent
            bbox = ",".join("%.7g"%ext[i] for i in (1, 0, 3, 2))
            ext_x = ext[2] - ext[0]
            ext_y = ext[3] - ext[1]
            size_x = max(1, int(200*(1.0 if ext_x > ext_y else ext_x/ext_y)))
            size_y = max(1, int(200*(1.0 if ext_y > ext_x else ext_y/ext_x)))

            return "".join([ URL,
                "SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap&STYLES=",
                "&FORMAT=image/png&DPI=96&TRANSPARENT=TRUE",
                "&CRS=EPSG:4326&WIDTH=%d&HEIGHT=%d"%(size_x, size_y),
                "&BBOX=%s"%bbox,
                "&LAYERS=%s"%coverage.identifier,
                ",%s_outlines"%coverage.identifier,
            ])

        def _kv(key, val):
            return '<tr><td>%s:</td><td>%s</td></tr>'%(key, val)

        def _eop2html(coverage):
            data_items = coverage.data_items
            data_items = data_items.filter(semantic="metadata", format="eogml")
            data_items = list(data_items)
            if len(data_items.count()) < 1:
                return

            with open(retrieve(data_items[0])) as fid:
                eop = etree.parse(fid)

            # extract metadata 

        yield '<html>'
        yield '<header>'
        yield '<style>\n'
        yield 'body { font-family: "Helvetica Neue",Helvetica,Arial,'\
                'sans-serif; font-size: 0.8em;}\n'
        yield '.title {font-weight:bold;}\n'
        yield '</style>'
        yield '</header>'
        yield '<body>'
        yield '<div class="title">%s</div>'%coverage.identifier
        yield '<div class="browse"><img src="%s" /></div>'%_get_browse_url(coverage)
        yield '<table>'
        yield _kv("crs", "EPSG:%d"%coverage.srid)
        yield _kv("size", "%d x %d pixels"%(coverage.size_x, coverage.size_y))
        yield _kv("bands", "%d"%(coverage.range_type.bands.count()))
        yield _kv("acq. start:", "%s"%(coverage.begin_time))
        yield _kv("acq. stop:", "%s"%(coverage.end_time))

        #self._original_begin_time = self.begin_time
        #self._original_end_time = self.end_time
        yield '</table>'
        yield '</body>'
        yield '</html>'
