#-------------------------------------------------------------------------------
#
# Local file-system files tracking.
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

import json
from django.conf import settings
from django.http import HttpResponse
from django.core.exceptions import ObjectDoesNotExist

from eoxserver.id2path.models import TrackedObject as TO
from eoxserver.id2path.models import PathItem as PI
from eoxserver.id2path.view_utils import (HttpError, error_handler,
    method_allow, ip_allow, ip_deny)
from eoxserver.resources.coverages.models import (RectifiedDataset,
    ReferenceableDataset)

# JSON formating options
#JSON_OPTS={}
JSON_OPTS = {'sort_keys': True, 'indent': 4, 'separators': (',', ': ')}

ALLOWED_KEYS = ("id", "filter", "coveragetype")
COV_TYPES = {
    "RectifiedDataset": RectifiedDataset,
    "ReferenceableDataset": ReferenceableDataset,
}


@error_handler                            # top error handler
@ip_deny(settings.ID2PATH_DENY_FROM)      # IP access black-list
@ip_allow(settings.ID2PATH_ALLOW_FROM)    # IP access white-list
@method_allow(['GET'])                    # HTTP method filter
def id2path(request):
    """ id2path view handler """

    # check the query string
    inputs = []
    for key, values in request.GET.lists():
        key = key.lower()
        if key.lower() not in ALLOWED_KEYS:
            raise HttpError(400, "Error: Bad request! Invalid key! KEY='%s'"%key)
        if len(values) > 1:
            raise HttpError(400, "Error: Bad request! Repeated key! KEY='%s'"%key)
        inputs.append((key, values[0]))
    inputs = dict(inputs)

    # check the inputs
    identifier = inputs.get("id", None)
    filters = inputs.get("filter", None)
    cov_type = inputs.get("coveragetype", None)

    if (identifier is None) and (filters is None):
        # return service signature if no input provided
        output = {"service": "id2path", "version": "1.0"}
        return HttpResponse(json.dumps(output, **JSON_OPTS), content_type="application/json")

    # find the tracked object matching the input identifier
    try:
        obj = TO.objects.get(identifier=identifier)
    except TO.DoesNotExist:
        raise HttpError(404, "Error: Record not found! Invalid identifier %r!"%identifier)

    # check the coverage type
    if cov_type is not None:
        try:
            COV_TYPES[cov_type].objects.get(identifier=identifier)
        except KeyError:
            raise HttpError(400, "Error: Unsupported coverage type %r!"%cov_type)
        except ObjectDoesNotExist:
            raise HttpError(404, "Error: No record found for the given coverage"
                " type %r and identifier %r!"%(cov_type, identifier))

    # check the filters
    filters = filters.split(',') if (filters is not None) else []
    try:
        types = [PI.STR2TYPE[s] for s in filters]
    except KeyError:
        raise HttpError(400, "Error: Bad request! Invalid filter!")

    # filter the records
    paths = obj.paths.all()
    if types:
        paths = paths.filter(type__in=types)

    # pack the response
    path_list = []
    for path in paths.all():
        item = {
            "url": "file://%s"%(path.path),
            "type": PI.TYPE2STR[path.type],
        }
        if path.label:
            item["label"] = path.label
        path_list.append(item)

    return HttpResponse(json.dumps(path_list, **JSON_OPTS), content_type="application/json")

