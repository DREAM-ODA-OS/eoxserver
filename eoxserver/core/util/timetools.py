#-------------------------------------------------------------------------------
#
# Project: EOxServer <http://eoxserver.org>
# Authors: Stephan Krause <stephan.krause@eox.at>
#          Stephan Meissl <stephan.meissl@eox.at>
#
#-------------------------------------------------------------------------------
# Copyright (C) 2011 EOX IT Services GmbH
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

import re
from datetime import datetime, timedelta

from django.utils.timezone import utc, make_aware, is_aware
from django.utils.dateparse import parse_datetime, parse_date


def isoformat(dt):
    """ Formats a datetime object to an ISO string. Timezone naive datetimes are
        are treated as UTC Zulu. UTC Zulu is expressed with the proper "Z" 
        ending and not with the "+00:00" offset declaration.
    """
    if not dt.utcoffset():
        dt = dt.replace(tzinfo=None)
        return dt.isoformat("T") + "Z"
    return dt.isoformat("T")


def parse_iso8601(value, tzinfo=None):
    """ Parses an ISO 8601 date or datetime string to a python date or datetime.
        Raises a `ValueError` if a conversion was not possible. The returned 
        datetime is always considered time-zone aware and defaulting to the 
        given timezone `tzinfo` or UTC Zulu if none was specified.
    """

    tzinfo = tzinfo or utc
    for parser in (parse_datetime, parse_date):
        try:
            temporal = parser(value)
        except Exception, e:
            raise ValueError(
                "Could not parse '%s' to a temporal value. "
                "Error was: %s" % (value, e)
            )
        if temporal:
            # convert to datetime if necessary
            if not isinstance(temporal, datetime):
                temporal = datetime.combine(temporal, datetime.min.time())

            # use UTC, if the datetime is not already time-zone aware
            if not is_aware(temporal):
                temporal = make_aware(temporal, tzinfo)
            
            return temporal

    raise ValueError("Could not parse '%s' to a temporal value" % value)


RE_ISO_8601 = re.compile(
    r"^(?P<sign>[+-])?P"
    r"(?:(?P<years>\d+(\.\d+)?)Y)?"
    r"(?:(?P<months>\d+(\.\d+)?)M)?"
    r"(?:(?P<days>\d+(\.\d+)?)D)?"
    r"T?(?:(?P<hours>\d+(\.\d+)?)H)?"
    r"(?:(?P<minutes>\d+(\.\d+)?)M)?"
    r"(?:(?P<seconds>\d+(\.\d+)?)S)?$"
)

def parse_duration(value):
    """ Parses an ISO 8601 duration string into a python timedelta object. 
        Raises a `ValueError` if a conversion was not possible.
    """
    
    match = RE_ISO_8601.match(value)
    if not match:
        raise ValueError(
            "Could not parse ISO 8601 duration from '%s'." % value
        )
    match = match.groupdict()

    sign = -1 if "-" == match['sign'] else 1
    days = float(match['days'] or 0)
    days += float(match['months'] or 0) * 30 #?!
    days += float(match['years'] or 0) * 365 #?!
    fsec = float(match['seconds'] or 0)
    fsec += float(match['minutes'] or 0) * 60
    fsec += float(match['hours'] or 0) * 3600

    return sign * timedelta(days, fsec)

