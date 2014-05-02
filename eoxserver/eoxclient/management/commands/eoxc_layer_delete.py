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
from django.db import transaction

#------------------------------------------------------------------------------

from eoxserver.eoxclient import models

from eoxserver.resources.coverages.management.commands import CommandOutputMixIn
from eoxserver.resources.coverages.management.commands import _variable_args_cb

#------------------------------------------------------------------------------

class Command(CommandOutputMixIn, BaseCommand):

    option_list = BaseCommand.option_list + (
        make_option("-i", "--id", "--identifier", dest="identifiers",
            action="callback", callback=_variable_args_cb, default=None,
            help=("Optional list of identifiers.")
        ),
    )

    args = "-i <id> [<id> ...]"

    help = ( """ Delete registered EOxClient layers.  """ )

    #--------------------------------------------------------------------------

    def handle(self, *args, **options):

        # statistic
        cl_removed = 0
        cl_failed  = 0
        cl_total   = 0

        #----------------------------------------------------------------------

        # Collect parameters

        self.verbosity = int(options.get('verbosity', 1))
        identifiers = options.get('identifiers',None)

        if identifiers is None :
            raise CommandError("Missing the required identifiers ('-i' option)!")

        #----------------------------------------------------------------------

        # get rid of any duplicate
        identifiers = set( identifiers )

        cl_total = len(identifiers)

        # prepare query set

        qset = models.ClientLayer.objects.all()
        qset = qset.filter( eoobj__identifier__in = identifiers )
        qset = qset.prefetch_related('eoobj')
        qset = qset.order_by('order','id')

        for item in qset :

            try:

                with transaction.commit_on_success() :
                    item.delete()

            except Exception as ex:
                cl_failed += 1
                self.print_err("Layer removal failed! ID='%s'"
                     " REASON=%s: %s"%(item.eoobj.identifier,type(ex),str(ex)))

            else :
                cl_removed += 1
                self.print_msg("Layer removed. ID='%s'"%item.eoobj.identifier)


        #----------------------------------------------------------------------
        # print final statistic

        cl_notfound =  cl_total - ( cl_removed + cl_failed )

        if 0 < cl_notfound :
            self.print_wrn("Some of the requested layers were not found!")

        self.print_msg("Layers removed:   %d of %d"%(cl_removed,cl_total))
        self.print_msg("Layers failed:    %d of %d"%(cl_failed,cl_total))
        self.print_msg("Layers not-found: %d of %d"%(cl_notfound,cl_total))
