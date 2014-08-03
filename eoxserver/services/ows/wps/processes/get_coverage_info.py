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
from eoxserver.core.config import get_eoxserver_config
from eoxserver.core import Component, implements
from eoxserver.resources.coverages.models import (
    Collection, Coverage, iscollection
)
from eoxserver.services.ows.wps.interfaces import ProcessInterface
from eoxserver.services.ows.wps.parameters import (
    LiteralData, ComplexData, CDTextBuffer, CDAsciiTextBuffer, FormatText,
    AllowedRange,
)
from eoxserver.services.ows.wps.exceptions import (
    ExecuteError, InvalidInputValueError,
    MissingRequiredInputError,
)

from .coverage_info import cov2html

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
        ("eoid", LiteralData("identifier", str, optional=True,
            title="Coverage or collection name.")),
        ("begin_time", LiteralData("begin_time", datetime, optional=True,
            title="Optional start of the time interval.")),
        ("end_time", LiteralData("end_time", datetime, optional=True,
            title="Optional end of the time interval.")),
        ("latitude", LiteralData("latitude", float, optional=True,
            title="Point of interest - latitude.",
            allowed_values=AllowedRange(-90.0, +90.0, dtype=float),
            uoms=(('dg', 1.0),))),
        ("longitude", LiteralData("longitude", float, optional=True,
            title="Point of interest - longitude.",
            allowed_values=AllowedRange(-180.0, +180.0, dtype=float),
            uoms=(('dg', 1.0),))),
    )

    outputs = (
        ("info", ComplexData("info", formats=FormatText('text/html'),
                    title="Coverage information in HTML format.")),
    )

    @classmethod
    def execute(cls, eoid, begin_time, end_time, latitude, longitude, **kwarg):
        """ The main execution function for the process.
        """
        # point of interest
        # the lat. and lon. must be provided together
        if latitude is None and longitude is not None:
            raise MissingRequiredInputError("latitude")
        elif latitude is not None and longitude is None:
            raise MissingRequiredInputError("longitude")
        elif latitude is not None and longitude is not None:
            point = Point(longitude, latitude, srid=4326)
        else:
            point = None

        # check whether the identifier is a collection or plain coverage
        try:
            eoobj = Collection.objects.get(identifier=eoid)
            is_collection = True
        except Collection.DoesNotExist:
            try:
                print "coverage:", eoid
                eoobj = Coverage.objects.get(identifier=eoid)
                is_collection = False
            except Coverage.DoesNotExist:
                raise InvalidInputValueError("identifier",
                                               "Invalid identifier '%s'!"%eoid)

        if is_collection:

            # recursive nested collection lookup
            def _get_children_ids(obj):
                id_list = [obj.id]
                for child in obj.eo_objects.all():
                    if iscollection(child):
                        id_list.extend(_get_children_ids(child.cast()))
                return id_list

            # prepare coverage query set
            coverages_qs = Coverage.objects.filter(
                                  collections__id__in=_get_children_ids(eoobj))
            if end_time is not None:
                coverages_qs = coverages_qs.filter(begin_time__lte=end_time)
            if begin_time is not None:
                coverages_qs = coverages_qs.filter(end_time__gte=begin_time)
            if point is not None:
                coverages_qs = coverages_qs.filter(footprint__contains=point)
            coverages_qs = coverages_qs.order_by('-begin_time', '-end_time',
                                                 '-identifier')
            try:
                coverage = coverages_qs[:1].get()
            except Coverage.DoesNotExist:
                coverage = None

        else: # is not collection
            coverage = eoobj
            if point is not None and not coverage.footprint.contains(point):
                coverage = None

        # create the output
        output = CDAsciiTextBuffer()

        if coverage is not None:
            for s in cov2html(coverage):
                output.write(s)

        return output
