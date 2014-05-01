#-------------------------------------------------------------------------------
#
# EOxClient integration interface - CLI
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

#------------------------------------------------------------------------------

from eoxserver.eoxclient import models
from eoxserver.eoxclient.views import layers2json
from eoxserver.resources.coverages import models as coverages 

from eoxserver.resources.coverages.management.commands import CommandOutputMixIn
from eoxserver.resources.coverages.management.commands import _variable_args_cb

#------------------------------------------------------------------------------

# JSON formating options
#opts={}
opts={ 'sort_keys':True,'indent':4,'separators':(',', ': ') }

#------------------------------------------------------------------------------

class Command(CommandOutputMixIn, BaseCommand):

    option_list = BaseCommand.option_list + (
        make_option('--json',
            dest='json_dump',
            action='store_true',
            default=False,
            help=("Optional. Full layers' dump in the JSON format." )
        ),
        make_option("-i", "--id", "--identifier", dest="identifiers", 
            action="callback", callback=_variable_args_cb, default=None,
            help=("Optional list of identifiers.")
        ),
    )

    args = "[-i <id> [<id> ...]]"

    help = ( """ Dump list of registered EOxClient layers.  """ )

    #--------------------------------------------------------------------------

    def handle(self, *args, **options):

        def id_list( qset ) : 
            l = []
            for item in qset : 
                l.append(item.eoobj.identifier)
            return "\n".join(l) 

        # Collect parameters
        self.verbosity = int(options.get('verbosity', 1))
        json_dump = bool(options.get('json_dump',False))
        identifiers = options.get('identifiers',None)

        # DB query-set 
        
        qset = models.ClientLayer.objects.all()
        qset = qset.prefetch_related('eoobj')

        if identifiers is not None : 
            qset = qset.filter( eoobj__identifier__in = identifiers ) 

        qset = qset.order_by('order','id') 
        
        # JSON 
        if json_dump : 
            output = layers2json( qset , opts ) 
        else : 
            output = id_list( qset ) 

        if output : 
            # print output 
            fid = sys.stdout 
            fid.write( output ) 
            fid.write( "\n" )  
