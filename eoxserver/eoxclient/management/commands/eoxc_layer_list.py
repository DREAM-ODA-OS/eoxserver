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

from eoxserver.resources.coverages.management.commands import CommandOutputMixIn
from eoxserver.resources.coverages.management.commands import _variable_args_cb

#------------------------------------------------------------------------------

# JSON formating options
#JSON_OPTS={}
JSON_OPTS={ 'sort_keys':True,'indent':4,'separators':(',', ': ') }

#------------------------------------------------------------------------------

class Command(CommandOutputMixIn, BaseCommand):

    option_list = BaseCommand.option_list + (
        make_option('--json',
            dest='json_dump',
            action='store_true',
            default=False,
            help=("Optional. Full layers' dump in the JSON format.")
       ),
        make_option('--flags',
            dest='flags_dump',
            action='store_true',
            default=False,
            help=("Optional. Dump flags to be passed to the create command.")
       ),
        make_option("-i", "--id", "--identifier", dest="identifiers",
            action="callback", callback=_variable_args_cb, default=None,
            help=("Optional list of identifiers.")
       ),
   )

    args = "[-i <id> [<id> ...]]"

    help = (""" Dump list of registered EOxClient layers.  """)

    #--------------------------------------------------------------------------

    def handle(self, *args, **options):

        #----------------------------------------------------------------------

        def unicode_escape(s):
            return unicode(s).encode("unicode_escape").replace("'",r'\x27')

        def layers2cliflags(qset) :
            l = []
            for item in qset :

                r = []

                r.append("--escaped")

                r.append("-i '%s'"%unicode_escape(item.eoobj.identifier))

                if item.name :
                    r.append("-n '%s'"%unicode_escape(item.name))

                if item.description :
                    r.append("-d '%s'"%unicode_escape(item.description))

                if item.wms_style :
                    r.append("-s '%s'"%unicode_escape(item.wms_style))

                if item.color :
                    r.append("-c '%s'"%unicode_escape(item.color))

                r.append(('--not-visible','--visible')[item.has_time])
                r.append(('--no-time','--time')[item.visible])
                r.append(('--referenceable','--rectified')[item.rectified])
                r.append(('--no-cloud-mask','--cloud-mask')[item.has_cloud_mask])
                r.append(('--no-snow-mask','--snow-mask')[item.has_snow_mask])

                l.append(" ".join(r))

            return "\n".join(l)

        def layers2idlist(qset) :
            l = []
            for item in qset :
                l.append(item.eoobj.identifier)
            return "\n".join(l)

        #----------------------------------------------------------------------

        # Collect parameters
        self.verbosity = int(options.get('verbosity', 1))
        json_dump = bool(options.get('json_dump',False))
        flags_dump = bool(options.get('flags_dump',False))
        identifiers = options.get('identifiers',None)

        # DB query-set

        qset = models.ClientLayer.objects.all()
        qset = qset.prefetch_related('eoobj')

        if identifiers is not None :
            qset = qset.filter(eoobj__identifier__in = identifiers)

        qset = qset.order_by('order','id')

        # JSON
        if json_dump :
            output = layers2json(qset, JSON_OPTS)
        elif flags_dump :
            output = layers2cliflags(qset)
        else :
            output = layers2idlist(qset)

        if output :
            # print output
            fid = sys.stdout
            fid.write(output)
            fid.write("\n")
