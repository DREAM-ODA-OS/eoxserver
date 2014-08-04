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

from eoxserver.contrib import mapserver as ms

from eoxserver.services.mapserver.wms.layers.base import (
    LayerFactory, StyledLayerMixIn, PolygonLayerMixIn,
)


class CoverageOutlinesVisibleLayerFactory(LayerFactory, PolygonLayerMixIn, StyledLayerMixIn):
    """ base coverage outline layer """

    def _outline_geom(self, cov):
        return cov.footprint

    def generate(self):
        layer = self._polygon_layer(self.group, filled=False, srid=4326)

        # initialize accumulator to an empty geometry
        accum = MultiPolygon([])

        count = 0
        for cov, cov_name in reversed(self.coverages):

            # get part of the visible footprint
            outline = self._outline_geom(cov) - accum

            # skip invisible outlines
            if outline.empty:
                continue

            # generate feature
            shape = ms.shapeObj.fromWKT(outline.wkt)
            shape.initValues(1)
            shape.setValue(0, cov_name)

            # add feature to the group
            layer.addFeature(shape)
            count += 1

            # update geometry accumulator
            accum = accum + self._outline_geom(cov)
       
        if count == 0: # add an empty feature if there is no applicable coverage 
            shape = ms.shapeObj()
            shape.initValues(1)
            shape.setValue(0, "__empty__")
            layer.addFeature(shape)

        yield layer, None, ()


class CoverageOutlinesVisibleMaskedLayerFactory(CoverageOutlinesVisibleLayerFactory):
    """ derived masked outlines' layer factory """

    def _outline_geom(self, cov):
        outline = cov.footprint
        for mask_item in cov.vector_masks.all():
            outline = outline - mask_item.geometry
        return outline
