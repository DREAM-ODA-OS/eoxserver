#-------------------------------------------------------------------------------
#
# EOxClient integration interface - DB model 
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
# The above copyright notice and this permission notice shall be included in
# all
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
from django.db import models
from django.core.exceptions import ValidationError

from eoxserver.resources.coverages import models as coverages

#-------------------------------------------------------------------------------

_gerexHexRGBColor = re.compile(r"^#[0-9a-f]{6,6}$",re.IGNORECASE)

def hex_rgb_color_validator( color ): 
    try: 
        if _gerexHexRGBColor.match(color) is None: 
            raise TypeError("No match!")
    except TypeError:         
        raise ValidationError("%s is not an RGB color string!"%(repr(color)))

class HexRGBColorField( models.CharField ): 
    
    description = "Hexadecimal RGB color."

    def __init__( self , *args , **kwargs ): 
        
        kwargs['max_length'] = 7 
        kwargs['validators'] = [hex_rgb_color_validator] 
        super(HexRGBColorField, self).__init__(*args, **kwargs)

    def deconstruct(self):
        # Django 1.7 feature 
        name, path, args, kwargs = super(HandField, self).deconstruct()
        del kwargs['max_length']
        del kwargs['validators']
        return name, path, args, kwargs

    def get_prep_value(self, value):
        return value.lower()

#-------------------------------------------------------------------------------

class ClientLayer(models.Model): 
    """ EOxClient layer """ 

    eoobj       = models.ForeignKey(coverages.DatasetSeries,related_name='+',
                                            verbose_name='Related EO Object' )
    order       = models.BigIntegerField(default=0) # ordering parameter
    name        = models.CharField(max_length=256, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    wms_style   = models.CharField(max_length=128, null=True, blank=True, 
                                          verbose_name='WMS style') 
    color       = HexRGBColorField(null=True,blank=True,
                                          verbose_name='Marker RGB color') 
    has_time    = models.BooleanField(null=False,default=True,
                                          verbose_name='Has time-dimension?') 
    visible     = models.BooleanField(null=False,default=False,
                                          verbose_name='Is visible?') 
    rectified   = models.BooleanField(null=False,default=True,
                                          verbose_name='Is rectified?') 
    has_cloud_mask = models.BooleanField(null=False,default=False,
                                          verbose_name='Has cloud-mask?') 
    has_snow_mask = models.BooleanField(null=False,default=False,
                                          verbose_name='Has snow-mask?') 

    def __unicode__(self):
        return ( self.name or self.eoobj.identifier ) 

    class Meta:
        verbose_name = "EOxClient Layer"
        verbose_name_plural = "EOxClient Layers"
