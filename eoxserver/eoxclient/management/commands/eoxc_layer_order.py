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
# default step of the order numbering 
DEFAULT_STEP=10

#------------------------------------------------------------------------------

class Command(CommandOutputMixIn, BaseCommand):

    option_list = BaseCommand.option_list + (
        make_option('-l','--list', dest='list_layers', action='store_true',
            default=False, help=("Optional. List layers and their ordering.")
        ),
        make_option('-r','--reorder',dest='reorder_layers',action='store_true',
            default=False, help=("Optional. Generate new layer order numbers")
        ),
        make_option('-s','--step',
            dest='step', action='store', type='int', default=DEFAULT_STEP,
            help=("Optional step in order numbering (default %d)."%DEFAULT_STEP)
        ),
        make_option("-o", "--order", dest="new_layer_orders",
            action="callback", callback=_variable_args_cb, default=None,
            help=("List of re-ordered items (<order>:<identifier>).")
        ),
    )

    args = "[-o <new-order>:<identifier> [<new-order>:<identifier> ...]]"

    help = ( """Manage order of the EOxClient layers.""" )

    #--------------------------------------------------------------------------

    def handle(self, *args, **options):

        #----------------------------------------------------------------------

        def update_order( layer , order ):

            id_ = layer.eoobj.identifier

            try:
                with transaction.commit_on_success():
                    layer.order = order
                    layer.save()

            except Exception as ex:
                raise CommandError("Layer order update failed! ID='%s'"
                        " ORDER=%d REASON=%s: %s"%(id_,order,type(ex),str(ex)))

            else:
                self.print_msg("Layer order updated. ID='%s'"
                                                       " ORDER=%d"%(id_,order))


        #----------------------------------------------------------------------

        fobj = sys.stdout

        # get the inputs

        list_layers      = options.get('list_layers',False)
        reorder_layers   = options.get('reorder_layers',False)
        new_layer_orders = options.get('new_layer_orders',[])
        step             = options.get('step',DEFAULT_STEP)

        #----------------------------------------------------------------------
        # handle new item orders

        if new_layer_orders is not None :

            for idx,item in enumerate(new_layer_orders):

                # parse the orders and identifiers

                order, _, id_ = item.partition(":")

                try:
                    order = int(order)
                except ValueError:
                    raise CommandError("Invalid order value! ITEM[%d]='%s'"
                                    " ORDER='%s'"%(idx+1,item,order))

                try:
                    layer = models.ClientLayer.objects.get(eoobj__identifier=id_)
                except:
                    raise CommandError("Invalid layer identifier! ITEM[%d]='%s'"
                                    " ID='%s'"%(idx+1,item,id_))

                # update order
                update_order(layer, order)

        #----------------------------------------------------------------------
        # reordering

        if reorder_layers:

            qset = models.ClientLayer.objects.all()
            qset = qset.prefetch_related('eoobj')
            qset = qset.order_by('order','id')

            for idx,item in enumerate(qset):

                # set new order
                update_order(item , idx*step)

        #----------------------------------------------------------------------
        # list layers and orders

        if list_layers:

            qset = models.ClientLayer.objects.all()
            qset = qset.prefetch_related('eoobj')
            qset = qset.order_by('order','id')

            for item in qset :
                fobj.write("%d:%s\n"%(item.order,item.eoobj.identifier))
