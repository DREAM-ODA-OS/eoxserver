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

import sys
import traceback

from optparse import make_option

from django.core.management.base import BaseCommand, CommandError
from django.core.paginator import Paginator 

## try the python default json module 
#try : import json 
#except ImportError: 
#    #try the original simplejson module
#    try: import simplejson as json
#    except ImportError: 
#        #try the simplejson module packed in django
#        try: import django.utils.simplejson as json 
#        except ImportError: 
#            raise ImportError( "Failed to import any usable json module!" ) 

#------------------------------------------------------------------------------
from eoxserver.id2path import models
from eoxserver.resources.coverages import models as cov_models 

from eoxserver.resources.coverages.management.commands import CommandOutputMixIn

#------------------------------------------------------------------------------
# special filters 

def filter_dummy( selection ): 
    """ dummy filter - pass the input unchnaged """
    return selection

#TODO: find a better way to filter the unbound items 
def filter_unbound( selection ): 
    """ filter unbound items """

    # get list of identifiers 
    ids = [ item.identifier for item in selection ] 

    # get list of EOObjects 
    eoobj = cov_models.EOObject.objects.filter( identifier__in = ids ) 
    eoobj_ids = [ item.identifier for item in eoobj ] 

    # proceed with the filtering 
    for item in selection : 
        if item.identifier not in eoobj_ids : 
            yield item 

def filter_empty( selection ): 

    for item in selection:
        if item.paths.count() == 0 : 
            yield item

#------------------------------------------------------------------------------

class Command(CommandOutputMixIn, BaseCommand):

    option_list = BaseCommand.option_list + (
#        make_option('--json',
#            dest='json_dump',
#            action='store_true',
#            default=False,
#            help=("Optional. Dump items in JSON format." )
#        ),
        make_option('-f','--full',
            dest='full_dump',
            action='store_true',
            default=False,
            help=("Optional. Full dump including files and " )
        ),
#        make_option('--path-only',
#            dest='list_path_only',
#            action='store_true',
#            default=False,
#            help=("Optional. Suppress printing of the path type identifers." ) 
#        ),
        make_option('--unbound',
            dest='list_unbound',
            action='store_true',
            default=False,
            help=("Optional. List unbound identifiers only, i.e., identifers " 
                  "for which no EO-Object exists." )
        ),
        make_option('--empty',
            dest='list_empty',
            action='store_true',
            default=False,
            help=("Optional. List empty identifiers only, i.e., identifers " 
                  "having no linked path item." )
        ),
        make_option('-i','--id','--identifier',
            dest='identifier',
            action='store', type='string',
            default=None,
            help=("Optional. Identifier for which the path is queried.") 
        ),
    )

    args = "[-i <identifier>]"

    help = (
    """
    When no identifier is given the command prints a list of the `id2path`
    registered objects. By default all object identifiers are printed. When 
    requested only the unbound, i.e., identifiers for which no EOObject exists
    are printed. 

    When an identifier is provided, than this object is printed. 

    By default only the objects' identifiers are printed. On demand the path
    items and their types are printed as well (full output). 
    """ 
    )

    #--------------------------------------------------------------------------

    def handle(self, *args, **options):

        # Collect parameters
        self.verbosity  = int(options.get('verbosity', 1))
        #print_json      = bool(options.get('json_dump',False))
        #list_path_only  = bool(options.get('list_path_only')) 
        full_dump       = bool(options.get('full_dump')) 
        list_unbound    = bool(options.get('list_unbound')) 
        list_empty      = bool(options.get('list_empty')) 

        identifier      = options.get('identifier',None)

        if list_unbound and list_empty : 
            raise CommandError( "The '--empty' and '--unbound' methods are "
                                "mutually exclusive." ) 

        #----------------------------------------------------------------------
        # object generators 

        def _get_all_objects(): 

            # pagination limit 
            N=256 

            # list identifiers 
            selection = models.TrackedObject.objects.all()
            selection = selection.prefetch_related('paths')
            paginator = Paginator( selection , N )

            _filter = filter_dummy 
            if list_unbound : _filter = filter_unbound 
            if list_empty :   _filter = filter_empty 


            # iterate over the pages 
            for i in xrange( paginator.num_pages ):
                for item in _filter( paginator.page(i+1) ):
                    yield item 


        def _get_selected_object(): 

            yield models.TrackedObject.objects.get( identifier = identifier )  


        def _check_if_unbound_path( tobj , path ): 

            # get the remaining owners 
            qs = path.owners.exclude( id = tobj.id )  

            # check whether all of them are unbound 
            return qs.count() == sum( 1 for _ in filter_unbound(qs) )

        #----------------------------------------------------------------------
        # output formaters  

        def _print_id( fid , item ): 
            fid.write( "%s\n"%( item.identifier ) ) 

        def _print_id_and_paths( fid , item ): 
            fid.write( "#%s\n"%( item.identifier ) ) 
            for path in item.paths.all() : 
                if (not list_unbound) or _check_if_unbound_path(item, path) : 
                    fid.write( "%s;%s;%s\n"%( path.path, path.typeAsStr,
                                                                path.label ) ) 

        #----------------------------------------------------------------------
        # generate the outputs 

        _generator = _get_selected_object if identifier else _get_all_objects
        _formater  = _print_id_and_paths if full_dump else _print_id

        #----------------------------------------------------------------------

        for item in _generator() : 
            _formater( sys.stdout , item )
