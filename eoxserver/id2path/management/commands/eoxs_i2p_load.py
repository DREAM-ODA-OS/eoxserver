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

# type-string to code conversion 
STR2TYPE = dict( (b,a) for (a,b) in PI.TYPE_CHOICES ) 

#------------------------------------------------------------------------------

class Command(CommandOutputMixIn, BaseCommand):

    option_list = BaseCommand.option_list + (
        make_option('-i','--id','--identifier',
            dest='identifier',
            action='store', type='string',
            default=None,
            help=("Optional. Identifier for which the paths will be loaded.") 
        ),
    )

    args = "[-i <identifier>]"

    help = (
    """
    This command loads 'id2path' path items from the standard input. The input 
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

    The labels are optional and can be omitted. The types can have one of the
    following values: 
      %s
    """ % ( "|".join( STR2TYPE.keys() ) )
    )
    #--------------------------------------------------------------------------


    def handle(self, *args, **options):
        
        # statistic 
        self.to_found  = 0 
        self.to_create = 0 
        self.pi_create = 0 
        self.pi_update = 0 
        self.pi_failure = 0 

        #----------------------------------------------------------------------
        # get or create tracked object 
        def _get_or_create_object( identifier ) :

            if identifier is None : return None 

            try: 

                tobj = TO.objects.get(identifier=identifier)

            except TO.DoesNotExist : 

                with transaction.commit_on_success(): 
                    tobj = TO.objects.create(identifier=identifier)

                self.to_create += 1 
                self.print_msg("New tracked object cretated."
                                                    " ID='%s'"%tobj.identifier)

            else : 

                self.to_found += 1 
                self.print_msg("An existing tracked object found."
                                                    " ID='%s'"%tobj.identifier)

            return tobj  

        #----------------------------------------------------------------------
        # create or update the path item 
        def _create_or_update_path( tobj, path, ptype, label ): 

            _label = "'%s'"%label if label else None  

            try: 

                #create the path item 
                with transaction.commit_on_success(): 
                    pitm = tobj.paths.create( owner=tobj, path=path, 
                                                    type=ptype, label=label ) 

            except IntegrityError : 

                #update the path item 
                with transaction.commit_on_success(): 
                    pitm = tobj.paths.filter( path=path ).update( 
                                                    type=ptype, label=label ) 

                self.pi_update += 1 
                self.print_msg( "An existing path item updated. ID='%s' PATH="
                    "'%s' TYPE=%s LABEL=%s"%(identifier,path,ptype,_label) ) 

            else : 

                self.pi_create += 1 
                self.print_msg( "New path item cretated. ID='%s' PATH='%s' "
                        "TYPE=%s LABEL=%s"%(identifier,path,ptype,_label) ) 

            return pitm 

        #----------------------------------------------------------------------


        # get input parameters 
        identifier  = options.get('identifier',None)

        # get the tracked object for the given identifier
        tobj = _get_or_create_object( identifier ) 

        # process the input stream 
        for line_num,line in enumerate( sys.stdin , 1 ) : 

            line = line.strip() 

            # skip empty lines 
            if len(line) == 0 : continue

            # identifier 
            if line[0] == '#' : 
                identifier = line[1:]
                tobj = _get_or_create_object( identifier )
                continue 

            # parse the line 
            tmp = line.split(";")
            
            path = tmp[0] 
            
            try: 
                ptype = STR2TYPE[tmp[1].lower()]
            except IndexError :
                self.pi_failure += 1 
                self.print_err("Line %i: Line ignored! Missing type field!"
                             " ID='%s' PATH='%s'"%(line_num,identifier,path))
                continue 
            except KeyError :
                self.pi_failure += 1 
                self.print_err("Line %i: Line ignored! Invalid type field!"
                   " ID='%s' PATH='%s' TYPE='%s'"%(line_num,identifier,path,tmp[1]))
                continue 

            label = None if ( len(tmp) < 3 ) else ( tmp[2] or None )  

            _create_or_update_path( tobj, path, ptype, label )


        # print final statistic 

        to_total = self.to_found + self.to_create 
        pi_total = self.pi_update + self.pi_create + self.pi_failure

        self.print_msg("Tracked Objects created:  %d of %d"%(self.to_create,to_total)) 
        self.print_msg("Path Items created:       %d of %d"%(self.pi_create,pi_total))
        self.print_msg("Path Items updtaed:       %d of %d"%(self.pi_update,pi_total)) 
        self.print_msg("Path Items failures:      %d of %d"%(self.pi_failure,pi_total)) 
