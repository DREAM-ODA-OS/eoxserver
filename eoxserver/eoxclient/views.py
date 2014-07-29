#-------------------------------------------------------------------------------
#
# EOxClient integration interface - Django view
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

import json
from django.http import HttpResponse
from eoxserver.core.config import get_eoxserver_config
from eoxserver.eoxclient import models
from eoxserver.eoxclient.view_utils import error_handler, method_allow

# JSON formating options
JSON_OPTS = {'sort_keys': True, 'indent': 4, 'separators': (',', ': ')}


def layers2json(selection, json_opts=None):
    """ convert EOxClient layers' selection to JSON """
    json_opts = (json_opts or {})

    # get the service URL
    url = get_eoxserver_config().get("services.owscommon", "http_service_url")
    if url and url[-1] == "?":
        url = url[:-1]

    # generate the layers' list
    layer_list = []
    for item in selection:
        id_ = item.eoobj.identifier
        layer = {
            "name": (item.name or id_),
            "description": (item.description or ""),
            "timeSlider": item.has_time,
            "timeSliderProtocol": "WPS",
            "visible": item.visible,
            "view": {
                "id": id_,
                "protocol": "WMS",
                "urls": [url],
                "style": (item.wms_style or "default"),
                #"cloudMask": item.has_cloud_mask,
                #"snowMask": item.has_snow_mask,
                "extraLayers": {},
            },
            "download": {
                "id": id_,
                "protocol": "EOWCS",
                "url": url,
                "rectified": item.rectified,
            },
            "info": {
                "id": "%s_outlines"%id_,
                "protocol": "WMS",
                "url": url,
            },
        }
        if item.color:
            layer['color'] = item.color
        layer_list.append(layer)

    return json.dumps({"products": layer_list}, **json_opts)


@error_handler # top error handler
@method_allow(['GET']) # HTTP method filter
def data_json(request):
    """ generate dynamically EOxClient's data sources (data.json) """
    qset = models.ClientLayer.objects.all()
    qset = qset.order_by('order', 'id')
    qset = qset.prefetch_related('eoobj')
    return HttpResponse(layers2json(qset, JSON_OPTS),
                                          content_type="application/json")

