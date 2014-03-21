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

from django.contrib.gis.geos.collections import MultiPolygon

from eoxserver.core.config import get_eoxserver_config
from eoxserver.core.decoders import config, typelist

from eoxserver.core import Component, implements
from eoxserver.contrib import mapserver as ms
from eoxserver.resources.coverages import models
from eoxserver.services.mapserver.interfaces import LayerPluginInterface

from eoxserver.resources.coverages.dateline import (
    extent_crosses_dateline, wrap_extent_around_dateline
)

from eoxserver.services.mapserver.wms.layers.base import (
    LayerFactory, StyledLayerMixIn, PolygonLayerMixIn,
)

#-------------------------------------------------------------------------------
from eoxserver.contrib import ogr 
#from eoxserver.contrib import osr
from osgeo import osr
from django.contrib.gis.geos import GEOSGeometry

class MaskLayerFactory(LayerFactory,PolygonLayerMixIn,StyledLayerMixIn): 

    def _mask( self, mask_items, outline ): 

        sr = osr.SpatialReference() 
        sr.ImportFromEPSGA(4326)

        #print sr.ExportToWkt()  

        mask = MultiPolygon(()) 
        
        for mask_item in mask_items: 

            ds = ogr.Open(mask_item.location) 
            ly = ds.GetLayer(0)
            ft = ly.GetFeature(0)
            g0 = ft.GetGeometryRef()
            g0.TransformTo( sr ) 

            # TODO: clip to outline 

            mask = mask | GEOSGeometry(buffer(g0.ExportToWkb())) 

        return mask

    def generate(self): 

        mask_name = self.suffix[1:] 
        semantic = "polygonmask[%s]"%mask_name 

        # keep the layer objects 
        d_groups = {} 

        # create the group layers 
        for group in self.groups : 
            layer = self._polygon_layer(group,filled=True,srid=4326)
            d_groups[group] = layer 
            yield layer, None, () 


        # iterate over the coverages and add features to the layer groups 
        for cov, group, cols in reversed( self.coverages ) : 

            # get the mask items
            mask_items = cov.data_items.filter(
                semantic__startswith=semantic
            )

            # get part of the visible footprint 
            mask = self._mask(mask_items,cov.footprint)

            # skip completly covered outlines 
            if mask.empty : continue 

            # generate feature 
            shape = ms.shapeObj.fromWKT(mask.wkt)
            shape.initValues(2)
            shape.setValue(0, cov.identifier)
            shape.setValue(1, mask_name)

            # add feature to the group
            d_groups[group].addFeature(shape)

#-------------------------------------------------------------------------------

class EnabledMasksConfigReader(config.Reader):
    section = "services.ows.wms"
    mask_names = config.Option(type=typelist(str, ","), default=[])

#-------------------------------------------------------------------------------

class MaskLayerPlugin(Component):
    implements(LayerPluginInterface)

    handles = (models.RectifiedDataset, models.RectifiedStitchedMosaic)
    requires_connection = True

    @property
    def suffixes(self):
        return ["_%s" % mask for mask in self.enabled_masks]

    @property
    def enabled_masks(self):
        decoder = EnabledMasksConfigReader(get_eoxserver_config())
        return decoder.mask_names

    def get_layer_factory(self,suffix,options):  
        factory = MaskLayerFactory(suffix,options)
        factory.plugin = self
        return factory 
