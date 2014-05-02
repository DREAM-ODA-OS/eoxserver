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

from django.http import HttpResponse

from eoxserver.core.config import get_eoxserver_config

from eoxserver.eoxclient import models
from eoxserver.eoxclient.view_utils import HttpError,error_handler,method_allow

# try the python default json module
try : import json
except ImportError:
    #try the original simplejson module
    try: import simplejson as json
    except ImportError:
        #try the simplejson module packed in django
        try: import django.utils.simplejson as json
        except ImportError:
            raise ImportError( "Failed to import any usable json module!" )

#-------------------------------------------------------------------------------

def layers2json( selection , json_opts=None ):
    """ convert EOxClient layers' selection to JSON """

    json_opts = ( json_opts or {} ) 

    # get the service URL
    url = get_eoxserver_config().get("services.owscommon","http_service_url")

    # generate the layers' list

    layer_list = []

    for item in selection :

        id_ = item.eoobj.identifier

        layer = {
            "name" : ( item.name or id_ ) ,
            "description" : ( item.description or "" ),
            "timeSlider" : item.has_time ,
            "visible" : item.visible ,
            "view" : {
                "id" : id_ ,
                "protocol" : "WMS" ,
                "urls" : [ url ] ,
                "style" : ( item.wms_style or "default" ) ,
                "cloudMask" : item.has_cloud_mask,
                "snowMask" : item.has_snow_mask,
            },
            "download" : {
                "id" : id_ ,
                "protocol" : "EOWCS" ,
                "url" : url ,
                "rectified" : item.rectified ,
            } ,
        }

        if item.color :
            layer['color'] = item.color

        layer_list.append( layer )

    return json.dumps( { "products": layer_list }  , **json_opts )

#-------------------------------------------------------------------------------

# JSON formating options
#JSON_OPTS={}
JSON_OPTS={ 'sort_keys':True,'indent':4,'separators':(',', ': ') }

#-------------------------------------------------------------------------------

@error_handler # top error handler
@method_allow( ['GET'] ) # HTTP method filter
def data_json( request ):
    """ generate dynamically EOxClient's data sources (data.json) """

    # query set
    qset = models.ClientLayer.objects.all()
    qset = qset.order_by('order','id')
    qset = qset.prefetch_related('eoobj')

    return HttpResponse( layers2json( qset, JSON_OPTS ),
                                          content_type="application/json" )

