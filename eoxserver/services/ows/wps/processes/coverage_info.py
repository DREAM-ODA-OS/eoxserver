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

from lxml import etree
from eoxserver.core.config import get_eoxserver_config
from eoxserver.core.util.timetools import isoformat
from eoxserver.backends.access import retrieve

# get the service URL
URL = get_eoxserver_config().get("services.owscommon", "http_service_url")

def eop_extract(eop):
    """ Extract EOP metadata from a parsed lxml element-tree object. """
    #TODO: fix the parsing of derived profiles

    def eop20(name):
        return "{http://www.opengis.net/eop/2.0}%s"%name
    def opt20(name):
        return "{http://www.opengis.net/opt/2.0}%s"%name
    def sar20(name):
        return "{http://www.opengis.net/sar/2.0}%s"%name
    def gml32(name):
        return "{http://www.opengis.net/gml/3.2}%s"%name

    def muti_namespace_find(xml, lname):
        for ns in [eop20, opt20, sar20]:
            elm = xml.find("//"+ns(lname))
            if elm is not None:
                return elm
        return None

    def _text(xml, path):
        elm = xml.find(path)
        return None if elm is None else elm.text

    def _text_uom(xml, path):
        elm = xml.find(path)
        return None if elm is None else "%s %s"%(elm.text, elm.get("uom"))

    md = {}

    base = "//"+eop20("Footprint")+"/"+eop20("centerOf")+"/"
    md["center"] = _text(eop, base+gml32("Point"))

    if md["center"]:
        md["center"] = [float(v) for v in md["center"].split(' ') if len(v)]

    base = "//"+eop20("Platform")+"/"
    md["platformName"] = _text(eop, base+eop20("shortName"))
    md["platformSID"] = _text(eop, base+eop20("serialIdentifier"))
    md["platformOrbitType"] = _text(eop, base+eop20("orbitType"))

    base = "//"+eop20("Instrument")+"/"
    md["instrumentName"] = _text(eop, base+eop20("shortName"))
    md["instrumentDescription"] = _text(eop, base+eop20("description"))
    md["instrumentType"] = _text(eop, base+eop20("instrumentType"))

    base = "//"+eop20("Sensor")+"/"
    md["sensorType"] = _text(eop, base+eop20("sensorType"))
    md["sensorResolution"] = _text(eop, base+eop20("resolution"))
    md["sensorOpMode"] = _text(eop, base+eop20("operationalMode"))
    md["sensorSwathId"] = _text(eop, base+eop20("swathIdentifier"))
    # TODO: wavelenghtInformation

    acq = muti_namespace_find(eop, "Acquisition")
    print acq
    base = "./"
    md["ascNodeDate"] = _text(acq, base+eop20("ascendingNodeDate"))
    md["ascNodeLongitude"] = _text(acq, base+eop20("ascendingNodeLongitude"))
    md["complTimeFromAscNode"] = _text(acq, base+eop20("completionTimeFromAscendingNode"))
    md["lastOrbitNumber"] = _text(acq, base+eop20("lastOrbitNumber"))
    md["orbitDirection"] = _text(acq, base+eop20("orbitDirection"))
    md["orbitDuration"] = _text(acq, base+eop20("orbitDuration"))
    md["orbitNumber"] = _text(acq, base+eop20("orbitNumber"))
    md["startTimeFromAscNode"] = _text(acq, base+eop20("startTimeFromAscendingNode"))
    md["wrsLatitudeGrid"] = _text(acq, base+eop20("wrsLatitudeGrid"))
    md["wrsLongitudeGrid"] = _text(acq, base+eop20("wrsLongitudeGrid"))
    md["sunAzimut"] = _text_uom(acq, base+eop20("illuminationAzimuthAngle"))
    md["sunZenit"] = _text_uom(acq, base+eop20("illuminationZenitAngle"))
    md["sunElevation"] = _text_uom(acq, base+eop20("illuminationElevationAngle"))
    md["instrAzimut"] = _text_uom(acq, base+eop20("instrumentAzimuthAngle"))
    md["instrZenit"] = _text_uom(acq, base+eop20("instrumentZenitAngle"))
    md["instrElevation"] = _text_uom(acq, base+eop20("instrumentElevationAngle"))
    md["incidence"] = _text_uom(acq, base+eop20("incidence"))
    md["acrossTrackIncidence"] = _text_uom(acq, base+eop20("acrossTrackIncidenceAngle"))
    md["alongTrackIncidence"] = _text_uom(acq, base+eop20("alongTrackIncidenceAngle"))
    md["pitch"] = _text_uom(acq, base+eop20("pitch"))
    md["roll"] = _text_uom(acq, base+eop20("roll"))
    md["yaw"] = _text_uom(acq, base+eop20("yaw"))

    #SAR specific metadata
    md["antennaLookDir"] = _text_uom(acq, base+eop20("antennaLookDirection"))
    md["dopplerFreq"] = _text_uom(acq, base+eop20("dopplerFrequency"))
    md["incidenceVariation"] = _text_uom(acq, base+eop20("incidenceAngleVariation"))
    md["maxIncidence"] = _text_uom(acq, base+eop20("maximumIncidenceAngle"))
    md["minIncidence"] = _text_uom(acq, base+eop20("minimumIncidenceAngle"))
    md["polarChannels"] = _text_uom(acq, base+eop20("polarisationChannels"))
    md["polarMode"] = _text_uom(acq, base+eop20("polarisationMode"))
    #todo sar:Acquisition

    res = muti_namespace_find(eop, "EarthObservationResult")
    md["cloudCovPercent"] = _text_uom(res, base+opt20("cloudCoverPercentage"))
    md["cloudCovAsConfidence"] = _text_uom(res, base+opt20("cloudCoverPercentageAssessmentConfidence"))
    md["cloudCovQuotationMode"] = _text_uom(res, base+opt20("cloudCoverPercentageQuotationMode"))
    md["snowCovPercent"] = _text_uom(res, base+opt20("snowCoverPercentage"))
    md["snowCovAsConfidence"] = _text_uom(res, base+opt20("snowCoverPercentageAssessmentConfidence"))
    md["snowCovQuotationMode"] = _text_uom(res, base+opt20("snowCoverPercentageQuotationMode"))

    # filter out missing values
    md_out = {}
    for key, val in md.iteritems():
        if val is not None:
            md_out[key] = val

    return md_out

def cov2html(coverage):
    """ Generate coverage HTML info."""
    ext = coverage.footprint.extent
    def _get_browse_url(coverage):
        bbox = ",".join("%.7g"%ext[i] for i in (1, 0, 3, 2))
        ext_x = ext[2] - ext[0]
        ext_y = ext[3] - ext[1]
        size_x = max(1, int(200*(1.0 if ext_x > ext_y else ext_x/ext_y)))
        size_y = max(1, int(200*(1.0 if ext_y > ext_x else ext_y/ext_x)))

        return "".join([URL,
            "SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap&STYLES=",
            "&FORMAT=image/png&DPI=96&TRANSPARENT=TRUE",
            "&CRS=EPSG:4326&WIDTH=%d&HEIGHT=%d"%(size_x, size_y),
            "&BBOX=%s"%bbox,
            "&LAYERS=%s"%coverage.identifier,
            ",%s_outlines"%coverage.identifier,
        ])

    def _lb(label, level=1):
        ind = "&nbsp;&nbsp;" * max(0, level)
        return '<tr><td colspan="2" class="italic">%s%s</td></tr>'%(ind, label)

    def _kv(key, val="", level=1):
        ind = "&nbsp;&nbsp;" * max(0, level)
        return '<tr><td>%s%s</td><td>%s</td></tr>'%(ind, key, val)

    def _eop2html(coverage):

        yield _lb("Earth Observation:", level=0)
        yield _lb("Phenomenom Time:", level=1)
        yield _kv("start:", "%s"%(isoformat(coverage.begin_time)), 2)
        yield _kv("stop:", "%s"%(isoformat(coverage.end_time)), 2)
        yield _lb("Spatial Metadata:", level=1)
        yield _kv("CRS:", "EPSG:%d"%coverage.srid, 2)
        yield _lb("Extent:", level=2)
        yield _kv("north:", "%.3f deg"%ext[3], 3)
        yield _kv("west:", "%.3f deg"%ext[0], 3)
        yield _kv("east:", "%.3f deg"%ext[2], 3)
        yield _kv("south:", "%.3f deg"%ext[1], 3)


        data_items = coverage.data_items
        data_items = data_items.filter(semantic="metadata", format="eogml")
        data_items = list(data_items)
        if len(data_items) < 1:
            return

        with open(retrieve(data_items[0])) as fid:
            eop = etree.parse(fid)

        # extract metadata
        md = eop_extract(eop)

        if md.get("center"):
            yield _lb("Center:", level=2)
            yield _kv("latitude:", "%.3f dg"%md["center"][0], 3)
            yield _kv("longitude:", "%.3f dg"%md["center"][1], 3)

        def _md(key, label, level=2):
            if md.get(key) is not None:
                return _kv(label, md[key], level)
            return ""

        yield _lb("Platform:", level=1)
        yield _md("platformName", "short name:")
        yield _md("platformSID", "serial identifier:")
        yield _md("platformOrbitType", "orbit type:")

        yield _lb("Instrument:", level=1)
        yield _md("instrumentName", "short name:")
        yield _md("instrumentDescription", "description:")
        yield _md("instrumentType", "type:")

        yield _lb("Sensor:", level=1)
        yield _md("sensorType", "type:")
        yield _md("sensorResolution", "resolution:")
        yield _md("sensorOpMode", "operational mode:")
        yield _md("sensorSwathId", "swath:")

        yield _lb("Acquisition:", level=1)
        yield _md("orbitDirection", "orbit direction:")
        yield _md("orbitDuration", "orbit duration:")
        yield _md("orbitNumber", "orbit number:")
        yield _md("lastOrbitNumber", "last orbit number:")
        yield _md("ascNodeDate", "asc.node date:")
        yield _md("ascNodeLongitude", "asc.node longitude:")
        yield _md("startTimeFromAscNode", "start time from asc.node:")
        yield _md("complTimeFromAscNode", "compl.time from asc.node:")
        yield _md("wrsLatitudeGrid", "WRS latitude:")
        yield _md("wrsLongitudeGrid", "WRS longitude:")
        yield _md("sunAzimut", "sun azimut:")
        yield _md("sunElevation", "sun elevation:")
        yield _md("sunZenit", "sun zenit:")
        yield _md("intrAzimut", "instrument azimut:")
        yield _md("intrElevation", "instrument elevation:")
        yield _md("intrZenit", "instrument zenit:")
        yield _md("incidence", "incidence angle:")
        yield _md("acrossTrackIncidence", "across track inc.:")
        yield _md("alongTrackIncidence", "along track inc.:")
        yield _md("pitch", "pitch")
        yield _md("roll", "roll")
        yield _md("yaw", "yaw")
        yield _md("antennaLookDir", "antenna look dir.:")
        yield _md("dopplerFreq", "doppler frequency")
        yield _md("incidenceVariation", "incidence ang.variation:")
        yield _md("maxIncidence", "max.incidence angle")
        yield _md("minIncidence", "min.incidence angle")
        yield _md("polarChannels", "polarisation channels:")
        yield _md("polarMode", "polarisation mode:")

        if md.get("cloudCovPercent") is not None:
            yield _lb("Cloud Cover:")
            yield _kv("percentage:", md["cloudCovPercent"], 2)
            yield _md("cloudCovAsConfidence", "assessment confidence:")
            yield _md("cloudCovQuotationMode", "quotation mode:")

        if md.get("snowCovPercent") is not None:
            yield _lb("Snow Cover:")
            yield _kv("percentage:", md["snowCovPercent"], 2)
            yield _md("snowCovAsConfidence", "assessment confidence:")
            yield _md("snowCovQuotationMode", "quotation mode:")


    yield '<!DOCTYPE html>'
    yield '<html>'
    yield '<head>'
    yield '<style>\n'
    yield 'body { font-family: "Helvetica Neue",Helvetica,Arial,'\
            'sans-serif; font-size: 0.8em;}\n'
    yield '.bold {font-weight:bold;}\n'
    yield '.italic {font-style:italic;}\n'
    yield '</style>'
    yield '</head>'
    yield '<body>'
    yield '<div class="bold">%s</div>'%coverage.identifier
    yield '<div><img src="%s" /></div>'%_get_browse_url(coverage)
    yield '<table>'
    yield _lb("Coverage Metadata:", level=0)
    yield _kv("subtype:", coverage.cast().__class__.__name__)
    yield _kv("source size:", "%d x %d pixels"%(coverage.size_x, coverage.size_y))
    yield _kv("source bands:", "%d"%(coverage.range_type.bands.count()))

    for item in _eop2html(coverage):
        yield item

    yield '</table>'
    yield '</body>'
    yield '</html>\n'
