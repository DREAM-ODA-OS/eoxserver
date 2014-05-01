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
from django.db.models import Max
from django.db.utils import IntegrityError

#------------------------------------------------------------------------------

from eoxserver.eoxclient import models

from eoxserver.resources.coverages.management.commands import CommandOutputMixIn

#------------------------------------------------------------------------------

class Command(CommandOutputMixIn, BaseCommand):

    option_list = BaseCommand.option_list + (
        make_option('-i','--id','--identifier',
            dest='identifier', action='store', type='string', default=None,
            help=("Mandatory DatasetSeries identifier.")
        ),
        make_option('-n','--name',
            dest='layer_name', action='store', type='string', default=None,
            help=("Optional verbose layer's name (defaults to the identifier).")
        ),
        make_option('-d','--description',
            dest='description', action='store', type='string', default=None,
            help=("Optional layer's description.")
        ),
        make_option('-s','--style','--wms-style',
            dest='wms_style', action='store', type='string', default=None,
            help=("Optional layer's WMS style (defaults to 'default').")
        ),
        make_option('-c','--color',
            dest='color', action='store', type='string', default=None,
            help=("Optional layer's label RGB color (hash-hexadecimal notation,"
                   " e.g., '#ff0000').")
        ),
        make_option('-o','--order',
            dest='order', action='store', type='int', default=None,
            help=("Optional layers list order (integer value).")
        ),
        make_option('--visible', dest='visible', action='store_true',
            default = False,
            help=("Optional. Enable layers initial visibility. " )
        ),
        make_option('--not-visible', dest='visible', action='store_false',
            help=("Optional. Disable layers initial visibility (default). " )
        ),
        make_option('--time', dest='time', action='store_true',
            default = True,
            help=("Optional. Enable time-dimension (default for a dataset-series).")
        ),
        make_option('--no-time', dest='time', action='store_false',
            help=("Optional. Disable time-dimension. " )
        ),
        make_option('--rectified', dest='rectified', action='store_true',
            default = True,
            help=("Optional. Indicate rectified datasets (default). " )
        ),
        make_option('--referenceable', dest='rectified', action='store_false',
            help=("Optional. Indicate referenceable datasets." )
        ),
        make_option('--cloud-mask', dest='cloud_mask', action='store_true',
            default = False,
            help=("Optional. Enable cloud masking." )
        ),
        make_option('--no-cloud-mask', dest='cloud_mask', action='store_false',
            help=("Optional. Disable cloud masking (default)." )
        ),
        make_option('--snow-mask', dest='snow_mask', action='store_true',
            default = False,
            help=("Optional. Enable snow masking." )
        ),
        make_option('--no-snow-mask', dest='snow_mask', action='store_false',
            help=("Optional. Disable snow masking (default)." )
        ),
        make_option('--escaped', dest='unicode_escaped', action='store_true',
            default = True,
            help=("Optional. Indicates the input strings are unicode-escaped"
                  " (i.e., encoded with the 'unicode_escape' codec)." )
        ),
    )

    args = "-i <id> [-n <name>][-d <desctription>]"

    help = ( """ Create or update EOxClient layer. """ )

    #--------------------------------------------------------------------------

    def handle(self, *args, **options):

        def get_default_order():
            o = models.ClientLayer.objects.aggregate(Max('order'))['order__max']
            return ( 0 if ( o is None ) else ( o + 10 ) )

        def codec_dummy(s):
            return ( None if ( s is None ) else unicode(s) )

        def codec_unicode_escaped(s):
            return ( None if ( s is None ) else s.decode("unicode_escape") )

        #----------------------------------------------------------------------

        eoobj_cls = models.ClientLayer.EOOBJ_CLASS

        # set the string codec
        codec = codec_dummy
        if options.get('unicode_escaped',False):
            codec = codec_unicode_escaped

        # extract input parameters
        order       = options.get('order',None)
        identifier  = codec( options.get('identifier',None) )
        name        = codec( options.get('layer_name',None) )
        description = codec( options.get('description',None) )
        wms_style   = codec( options.get('wms_style',None) )
        color       = codec( options.get('color',None) )
        visible     = options.get('visible',False)
        time        = options.get('time',True)
        rectified   = options.get('rectified',True)
        cloud_mask  = options.get('cloud_mask',False)
        snow_mask   = options.get('snow_mask',False)

        if identifier is None:
            raise CommandError("Missing the %s identifier ('-i' option)!"
                               ""% eoobj_cls.__name__ )

        #----------------------------------------------------------------------
        # locate the linked EOObject

        try:

            eoobj = eoobj_cls.objects.get( identifier = identifier )

        except eoobj_cls.DoesNotExist:
            raise CommandError("No %s found matching the given identifier!"
                               " ID='%s'"%( eoobj_cls.__name__ , identifier ) )
        else:
            self.print_msg("%s matching the given identifier found."
                               " ID='%s'"%( eoobj_cls.__name__ , identifier ) )

        #----------------------------------------------------------------------
        # create the Client's Layer

        layer_prm = {
            'visible': visible ,
            'rectified': rectified ,
            'has_cloud_mask': cloud_mask ,
            'has_snow_mask': snow_mask ,
            'has_time': time ,
            'order': ( get_default_order() if ( order is None ) else order )
        }

        if name is not None:
            layer_prm['name'] = name

        if description is not None:
            layer_prm['description'] = description

        if wms_style is not None:
            layer_prm['wms_style'] = wms_style

        if color is not None:
            layer_prm['color'] = color

        #----------------------------------------------------------------------
        # create the Client's Layer

        try:

            with transaction.commit_on_success():
                eoobj_cls = models.ClientLayer.objects.create(
                            eoobj = eoobj, **layer_prm )

        except IntegrityError:

            self.print_msg("The layer already exists. Forcing layer's update."
                                                      " ID='%s'"% identifier )

            #------------------------------------------------------------------
            # update the Client's layer

            # avoid default re-ordering
            if order is None:
                del layer_prm['order']

            try:

                with transaction.commit_on_success():
                    obj = models.ClientLayer.objects.get( eoobj_id = eoobj.id )
                    for field in layer_prm:
                        setattr( obj , field , layer_prm[field] )
                    obj.save()

            except Exception as ex:
                raise CommandError("Layer update failed! ID='%s'"
                               " REASON=%s: %s"%(identifier,type(ex),str(ex)))

            else:
                self.print_msg("New layer updated successfully."
                                                       " ID='%s'"% identifier )

            #------------------------------------------------------------------

        except Exception as ex:
            raise CommandError("Layer creation failed! ID='%s'"
                               " REASON=%s: %s"%(identifier,type(ex),str(ex)))

        else:
            self.print_msg("New layer created successfully."
                                                      " ID='%s'"%identifier)

        #----------------------------------------------------------------------
