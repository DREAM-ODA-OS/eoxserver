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
from django.core.management.base import BaseCommand, CommandError
from django.core.paginator import Paginator
from eoxserver.id2path.models import TrackedObject as TO
from eoxserver.id2path.models import PathItem as PI
#from eoxserver.id2path import models
from eoxserver.resources.coverages.models import EOObject
from eoxserver.resources.coverages.management.commands import CommandOutputMixIn

#------------------------------------------------------------------------------
# special filters

def filter_dummy(selection):
    """ dummy filter - pass the input unchnaged """
    return selection

def _get_bound_ids(selection):
    # get list of identifiers
    ids_all = [item.identifier for item in selection]
    #TODO: find a better way to filter the unbound items
    # get list of bound ids
    eoobj = EOObject.objects.filter(identifier__in=ids_all)
    ids_bound = [item.identifier for item in eoobj]
    return ids_bound

def filter_unbound(selection):
    """ filter unbound items """
    ids_bound = _get_bound_ids(selection)
    # proceed with the filtering
    for item in selection:
        if item.identifier not in ids_bound:
            yield item

def all_unbound(selection):
    """ check whether all items are unbound """
    ids_bound = _get_bound_ids(selection)
    return len(ids_bound) == 0


def filter_empty(selection):
    """ filter items having no path items registered """
    for item in selection:
        if item.paths.count() == 0:
            yield item

#------------------------------------------------------------------------------

class Command(CommandOutputMixIn, BaseCommand):

    option_list = BaseCommand.option_list + (
        make_option('-f', '--full',
            dest='full_dump',
            action='store_true',
            default=False,
            help=("Optional. Full dump including path items.")
       ),
        make_option('--unbound',
            dest='list_unbound',
            action='store_true',
            default=False,
            help=("Optional. List unbound identifiers only, i.e., identifers "
                  "for which no EO-Object exists. When full dump requested "
                  "all path items are printed, i.e., even those linked with "
                  "another bound tracked object. The listed items can be "
                  "passed to the 'eoxs_i2p_delete' commands, but cannot "
                  "safely removed from the filesystem.")
       ),
        make_option('--unbound-strict',
            dest='list_unbound_strict',
            action='store_true',
            default=False,
            help=("Optional. List unbound identifiers only, i.e., identifers "
                  "for which no EO-Object exists. When full dump requested "
                  "only the strictly unbound path items are printed, i.e., "
                  "those linked with another bound tracked object are "
                  "suppressed. The listed files and directories can be safely "
                  "removed from the filesystem.")
       ),
        make_option('--empty',
            dest='list_empty',
            action='store_true',
            default=False,
            help=("Optional. List empty identifiers only, i.e., identifers "
                  "having no linked path item.")
       ),
        make_option('-i', '--id', '--identifier',
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
        full_dump = bool(options.get('full_dump'))
        list_unbound = bool(options.get('list_unbound'))
        list_unbound_strict = bool(options.get('list_unbound_strict'))
        list_empty = bool(options.get('list_empty'))
        identifier = options.get('identifier', None)
        list_unbound = (list_unbound or list_unbound_strict)

        if list_unbound and list_empty:
            raise CommandError("The '--empty', '--unbound' and "
                    "'--unbound-strict' methods are mutually exclusive.")

        #----------------------------------------------------------------------
        # object generators

        def _get_all_objects():
            nitems = 256 # pagination limit
            selection = TO.objects.all()
            selection = selection.prefetch_related('paths')
            paginator = Paginator(selection, nitems)
            _filter = filter_dummy
            if list_empty:
                _filter = filter_empty
            elif list_unbound:
                _filter = filter_unbound
            for i in xrange(paginator.num_pages):
                for item in _filter(paginator.page(i+1)):
                    yield item

        def _get_selected_object():
            try:
                yield TO.objects.get(identifier=identifier)
            except TO.DoesNotExist:
                pass

        def _check_if_unbound_path(path, exlude_tobj=None):
            qset = path.owners.all()
            if exlude_tobj is not None:
                qset = qset.exclude(id=exlude_tobj.id)
            if not all_unbound(qset):
                return False
            if path.type != path.DIRECTORY:
                # no - it is a file
                return True
            else:
                # yes - it is a directory
                # find path items contaning this directory
                qset2 = PI.objects.exclude(id=path.id)
                qset2 = qset2.filter(path__startswith=path.path)
                # if any of them bound set this item as bound as well
                for item in qset2:
                    if not _check_if_unbound_path(item):
                        return False
                return True

        #----------------------------------------------------------------------
        # output formaters

        def _print_id(fid, item):
            fid.write("%s\n"%(item.identifier))

        def _print_id_and_paths(fid, item):
            fid.write("#%s\n"%(item.identifier))
            for path in item.paths.all():
                if (not list_unbound_strict) or _check_if_unbound_path(path, item):
                    items = [path.path, path.type_as_str]
                    if path.label:
                        items.append(path.label)
                    fid.write("%s\n"%(";".join(items)))

        #----------------------------------------------------------------------
        # generate the outputs

        _generator = _get_selected_object if identifier else _get_all_objects
        _formater = _print_id_and_paths if full_dump else _print_id

        for item in _generator():
            _formater(sys.stdout, item)
