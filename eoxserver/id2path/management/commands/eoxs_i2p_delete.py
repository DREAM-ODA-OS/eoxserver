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
from django.db.utils import IntegrityError 
from django.db import transaction

#------------------------------------------------------------------------------

from eoxserver.id2path.models import TrackedObject as TO 
from eoxserver.id2path.models import PathItem as PI 
from eoxserver.resources.coverages.management.commands import CommandOutputMixIn
from eoxserver.resources.coverages.management.commands import _variable_args_cb

# type-string to code conversion 
STR2TYPE = dict( (b,a) for (a,b) in PI.TYPE_CHOICES ) 

#------------------------------------------------------------------------------

class Command(CommandOutputMixIn, BaseCommand):

    option_list = BaseCommand.option_list + (
#        make_option('-i','--id','--identifier',
#            dest='identifiers',
#            action="callback", callback=_variable_args_cb,
#            default=None,
#            help=("Optional. Identifiers of the tracked objects to be removed.") 
#        ),
#        make_option('-p','--path'
#            dest='paths',
#            action="callback", callback=_variable_args_cb,
#            default=None,
#            help=("Optional. Path Items to be removed.") 
#        ),
        make_option('-i','--id','--identifier',
            dest='identifier',
            action='store', type='string',
            default=None,
            help=("Optional. Identifier for which the path is removed.") 
        ),
        make_option('--remove-empty',
            dest='remove_empty',
            action='store_true',
            default=False,
            help=("Optional. Force removal of empty objects. By default, the"
                  " tracked object remain registered.") 
        ),
    )

    args = "[-i <identifier>]"

    help = (
    """
    This command deletes 'id2path' path items and/or tracked objects. The input 
    is expected to be the same as the full output of the 'list' command:

      - any line starting by the hash character resets the identfier;
      - any other line is expected to be the collon separated path record. 
      - empty lines are ignored 

    Sample: 

    #<identifier no.1>
    <path 1.1>;<type 1.1>;<label 1.1> 
    <path 1.2>;<type 1.2>;<label 1.2> 
    #<identifier no.2>
    <path 2.1>;<type 2.1>;<label 2.1> 
    <path 2.2>;<type 2.2>;<label 2.2> 

    The types and labels are ignored and can be omited. The use of the object
    identifiers is optional but recomended in cases when one path is used 
    mutiple times. If the tracked object is not specified all path items 
    from multiple objects are removed. 
    """ 
    )
    #--------------------------------------------------------------------------

    def handle(self, *args, **options):

        # flag 
        self.to_invalid = False 
        
        # statistic 
        self.to_found   = 0 
        self.to_failure = 0 
        self.to_remove  = 0 
        self.to_rfailure = 0 
        self.pi_found   = 0 
        self.pi_remove  = 0 
        self.pi_unlink  = 0 
        self.pi_abort   = 0 
        self.pi_failure = 0 

        #----------------------------------------------------------------------
        # get an existing tracked object 

        def _get_object( identifier ):

            self.to_invalid = False 

            if identifier is None : return None 

            try: 

                tobj = TO.objects.get(identifier=identifier)

            except TO.DoesNotExist : 

                tobj = None 

                self.to_invalid = True
                self.to_failure += 1 
                self.print_err("Tracked object not found! Subsequent path"
                               " items' removals will be aborted! ID='%s'"
                                                                ""%identifier)

            else : 

                self.to_found += 1 
                self.print_msg("An existing tracked object found."
                                                    " ID='%s'"%tobj.identifier)

            return tobj  

        #----------------------------------------------------------------------
        # remove tracked object if it has no path items 

        def _remove_object_if_empty( tobj ): 

            if tobj is None : return 

            if tobj.paths.count() > 0 : 
                return 
                
            try: 
                with transaction.commit_on_success() :
                    tobj.delete()

            except Exception as e : 
                self.to_rfailure += 1
                self.print_msg( "Tracked object removal failed! ID='%s'"
                            " REASON=%s: %s"%(tobj.identifier,type(e),str(e)) )

            else : 
                self.to_remove += 1 
                self.print_msg( "Tracked object removed. ID='%s'"
                                                          ""%tobj.identifier )


        #----------------------------------------------------------------------
        # remove path item

        def _remove_path( tobj, path ): 

            remove_pitm = False 

            # check the abort flag 
            if self.to_invalid : 
                self.pi_abort += 1
                self.print_wrn( "Path item removal aborted! PATH='%s'"%path )
                return 


            # case 1 - no tracked object given - the path items will be removed

            if tobj is None : 
                
                # lookup the path item 
                try: 

                    pitm = PI.objects.get( path = path ) 

                except PI.DoesNotExist :
                    self.pi_failure += 1
                    self.print_err( "Path item not found! PATH='%s'"%path )
                    return 

                else : 
                    self.pi_found += 1 


            # case 2 - tracked object given - relation to the tracked object 
            #          will be removed and the path item will be removed if 
            #          relation has left 
                
            else : 

                # lookup the path item 
                try: 

                    pitm = tobj.paths.get( path = path )

                except PI.DoesNotExist :
                    self.pi_failure += 1
                    self.print_err( "Path item not found for the given tracked"
                                    " object! ID='%s' PATH='%s'"%( 
                                                      tobj.identifier, path ) ) 
                    return 

                else : 
                    self.pi_found += 1 

                # path item has multiple owners - not to be removed!
                if pitm.owners.exclude( id = tobj.id ).count() > 0 : 
        
                    # unlink the path object relation relation 
                    try: 

                        with transaction.commit_on_success(): 
                            pitm.owners.remove( tobj ) 

                    except Exception as e : 
                        self.pi_failure += 1
                        self.print_msg( "Path item unlinking failed! ID='%s'"
                                        " PATH='%s' REASON=%s: %s"%(
                                         tobj.identifier,path,type(e),str(e)) )

                    else : 
                        self.pi_unlink += 1 
                        self.print_msg( "Path item unlinked from the tracked"
                                        " object. ID='%s' PATH='%s'"%(
                                                      tobj.identifier, path ) ) 
                    return  

                # path has only one owner - shall be removed 
                #else : pass


            try: 
                with transaction.commit_on_success(): 
                    pitm.delete()

            except Exception as e : 
                self.pi_failure += 1
                self.print_msg( "Path item removal failed! PATH='%s'"
                                " REASON=%s: %s"%(path,type(e),str(e)) )

            else : 
                self.pi_remove += 1 
                self.print_msg( "Path item removed PATH='%s'"%path )


        #----------------------------------------------------------------------

        # get input parameters 
        identifier   = options.get('identifier',None)
        remove_empty = options.get('remove_empty',False) 

        # get the tracked object for the given identifier
        tobj = _get_object( identifier ) 

        # process the input stream 
        for line_num,line in enumerate( sys.stdin , 1 ) : 

            line = line.strip() 

            # skip empty lines 
            if len(line) == 0 : continue

            # object identifier 
            if line[0] == '#' : 
                identifier = line[1:]
                if remove_empty : 
                    _remove_object_if_empty( tobj ) 
                tobj = _get_object( identifier )
                continue 

            # parse the line 
            tmp = line.split(";")
            
            path = tmp[0] # NOTE: anything else than the path is ignored 

            _remove_path( tobj, path )

        if remove_empty : 
            _remove_object_if_empty( tobj ) 

        #----------------------------------------------------------------------
        # print final statistic 

        to_total = self.to_found + self.to_failure
        pi_total = self.pi_remove + self.pi_unlink + self.pi_abort + self.pi_failure

        self.print_msg("Tracked Objects removed:  %d of %d"%(self.to_remove,to_total)) 
        self.print_msg("Tracked Objects failed:   %d of %d"%(self.to_failure,to_total)) 
        self.print_msg("Path Items removed:       %d of %d"%(self.pi_remove,pi_total))
        self.print_msg("Path Items unlinked:      %d of %d"%(self.pi_unlink,pi_total)) 
        self.print_msg("Path Items aborted:       %d of %d"%(self.pi_abort,pi_total)) 
        self.print_msg("Path Items failed:        %d of %d"%(self.pi_failure,pi_total)) 

