#-------------------------------------------------------------------------------
#
# Local file-system files tracking.
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

from eoxserver.id2path import models 

import json 
import ipaddr

TYPE2STR = dict( models.PathItem.TYPE_CHOICES ) 

#opts={}
opts={ 'sort_keys':True,'indent':4,'separators':(',', ': ') } 


class HttpError(Exception):
    """ Simple HTTP error exception """
    
    def __init__( self , status , message ) : 
        self.status = status 
        self.message = message 

    def __unicode__( self ): 
        return "%d %s"%( self.status , self.message ) 

#-------------------------------------------------------------------------------

def error_handler( view ):
    """ error handling decorator """ 

    def _wrapper_( request ): 

        try: 

            return view( request ) 
        
        except HttpError as e : 
            response =  HttpResponse(unicode(e),content_type="text/plain")
            response.status_code = e.status 
            return response 

    _wrapper_.__name__ = view.__name__ 
    _wrapper_.__doc__ = view.__doc__ 

    return _wrapper_


def ip_white_list( ip_list ):
    """ IP white-list restricted access """ 

    def _wrap_( view ) : 
        def _wrapper_( request ): 

            # request source address 
            ip_src = ipaddr.IPAddress( request.META['REMOTE_ADDR'] ) 

            # loop over the allowed addresses
            for ip in ip_list : 
                if ip_src in ipaddr.IPNetwork( ip ) : 
                    break 
            else :
                raise HttpError( 403, "Forbiden!" ) 

            return view( request ) 
            
        _wrapper_.__name__ = view.__name__ 
        _wrapper_.__doc__ = view.__doc__ 

        return _wrapper_
    return _wrap_ 
#-------------------------------------------------------------------------------

# todo move into the configuration 
ip_list = [ '0.0.0.0/0' , '127.0.0.1' ]

@error_handler
@ip_white_list( ip_list ) 
def id2path( request ): 
    """ id2path view handler """ 
    
    keys = ( "id" , "filter" ) 

    #--------------------------------------------------------------------------
    # check the method
    if request.method != 'GET' : 
        raise HttpError( 405 , "Error: Method not supported!"
                                            " METHOD='%s'"%request.method ) 

    #--------------------------------------------------------------------------
    # check the query string 
    inputs = [] 
    for key,values in request.GET.lists() : 
        key = key.lower()
        if key.lower() not in keys : 
            raise HttpError( 400, "Error: Bad request! Invalid key!"
                                                        " KEY='%s'"%key ) 
        if len(values) > 1 : 
            raise HttpError( 400, "Error: Bad request! Repeates key!"
                                                        " KEY='%s'"%key ) 
        inputs.append( (key,values[0]) ) 

    inputs = dict(inputs) 

    #--------------------------------------------------------------------------
    # check the inputs 

    identifier = inputs.get("id",None) 
    filters    = inputs.get("filter",None) 

    # print service signature if no input provided 

    if ( identifier is None ) and ( filters is None ) : 
        r = { "service":"id2path" , "version" : "1.0" } 
        return HttpResponse( json.dumps( r , **opts ),
                                          content_type="application/json" )

    # find the tracked object matching the input identifier

    try: 

        obj = models.TrackedObject.objects.get( identifier = identifier )

    except models.TrackedObject.DoesNotExist : 

        raise HttpError( 404, "Error: Record not found! Invalid"
                                " identifier! IDENTIFIER='%s'"%identifier ) 

    # check the filters 
        
    filters    = filters.split(',') if ( filters is not None ) else [] 

    for f in filters : 
        if f not in models.PathItem.TYPE_STRINGS : 
            raise HttpError( 400, "Error: Bad request! Invalid filter!"
                                                        " FILTER='%s'"%f )

    #--------------------------------------------------------------------------
    # filter the records 

    paths = obj.paths.all() 

    #--------------------------------------------------------------------------
    # pack the response 

    l = [] 

    for path in paths.all() :
        
        l.append( { "url" : "file://%s"%( path.path ) , 
                    "type"    : TYPE2STR[ path.type ] } ) 

    return HttpResponse( json.dumps( l , **opts ),
                                          content_type="application/json" )

    #--------------------------------------------------------------------------

