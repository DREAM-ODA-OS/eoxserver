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

from django.core.exceptions import ValidationError
from django.core.management.base import CommandError, BaseCommand
from django.utils.dateparse import parse_datetime
from django.db import transaction
from django.contrib.gis.geos import GEOSGeometry

from eoxserver.resources.coverages.management.commands import (
    CommandOutputMixIn, _variable_args_cb
)

from eoxserver.resources.coverages.models import EOObject

class Command(CommandOutputMixIn, BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option("-i", "--identifier", dest="identifier",
            action="store", default=None,
            help=("Queried identifier.")
        ),
        make_option("-s","--semantic",dest="semantic", 
            action="store", default=None, 
            help=("Optional. Metadata semantic (key).")
        ),
    )

    args = "-i <id> [-s <semantic>]"

    help = (
    """
    Print EOObject metadata. The metadada are simple key (semantic), value
    pairs assigned to an EOObject. In case of no semantic specified, all metadata 
    items will be printed. 
    """ 
    )

    def handle(self, *args, **opt):

        #----------------------------------------------------------------------
        # check the inputs 

        # check required identifier 
        identifier = opt.get('identifier',None)
        if identifier is None : 
            raise CommandError("Missing the mandatory dataset identifier!")

        # get semantic 
        semantic = opt.get('semantic',None) 

        #----------------------------------------------------------------------
        # perform the action 
   
        # find the EOObj matching the identifier
        try :  

            eoobj = EOObject.objects.get(identifier=identifier).cast()

        except eotype.DoesNotExist : 

            self.print_err( "There is no EOObject matching the identifier: "
                    "'%s'" % identifier )  
            
            #TODO: Find a better way how to pass the return code.
            sys.exit(1) 

        else : 

            self.print_msg( "There is a %s matching the identifier: '%s'" % ( 
                eoobj.__class__.__name__, identifier ) )  

        # list the metadata items assigned to the EOObject 

        metadata_items = eoobj.metadata_items.all() 

        if semantic is not None : 
            metadata_items = metadata_items.filter( semantic=semantic ) 

        for md in metadata_items: 
            print "%s\t\"%s\""%( md.semantic , md.value ) 
            
        #----------------------------------------------------------------------



