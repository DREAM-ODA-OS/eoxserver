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
#import traceback
from optparse import make_option
from django.core.management.base import CommandError, BaseCommand
from eoxserver.resources.coverages.models import EOObject, MetadataItem
from eoxserver.resources.coverages.management.commands import (
    CommandOutputMixIn
)

class Command(CommandOutputMixIn, BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option("-i", "--identifier", dest="identifier",
            action="store", default=None,
            help=("Queried identifier.")
        ),
        make_option("-s", "--semantic", dest="semantic",
            action="store", default=None,
            help=("Metadata semantic (key).")
        ),
        make_option("-l", "--value", dest="value",
            action="store", default=None,
            help=("Metadata value.")
        ),
    )

    args = "-i <id> -s <semantic> -l <value>"

    help = (
    """
    Set EOObject metadata. The metadada are simple key (semantic), value
    pairs assigned to an EOObject. This command sets a new key/value pair.
    """
    )

    def handle(self, *args, **opt):
        identifier = opt.get('identifier', None)
        if identifier is None:
            raise CommandError("Missing the mandatory dataset identifier!")

        semantic = opt.get('semantic', None)
        if semantic is None:
            raise CommandError("Missing the mandatory metadata semantic!")

        value = opt.get('value', None)
        if value is None:
            raise CommandError("Missing the mandatory metadata value!")

        try:
            eoobj = EOObject.objects.get(identifier=identifier).cast()
        except EOObject.DoesNotExist:
            self.print_err("There is no EOObject matching the identifier: "
                    "'%s'" % identifier)
            #TODO: Find a better way how to pass the return code.
            sys.exit(1)
        else:
            self.print_msg("There is a %s matching the identifier: '%s'" % (
                eoobj.__class__.__name__, identifier))

        # set the metadata item if not already set
        tmp = eoobj.metadata_items.filter(semantic=semantic, value=value)
        if tmp.count() == 0:
            md = MetadataItem()
            md.semantic = semantic
            md.value = value
            md.eo_object = eoobj
            md.full_clean()
            md.save()
            self.print_msg("Metadata item '%s' created successfully."%semantic)
        else:
            self.print_msg("Metadata item '%s' with the same value already"
                    " exists. Nothing is done."%semantic)

