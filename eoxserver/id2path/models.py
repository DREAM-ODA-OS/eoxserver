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

import logging
import os.path

from django.db import models

logger = logging.getLogger(__name__)

#-------------------------------------------------------------------------------

class TrackedObject(models.Model):
    """ tracked object """

    time_created = models.DateTimeField("Created",auto_now_add=True)
    time_updated = models.DateTimeField("Last update",auto_now=True)

    identifier = models.CharField(max_length=256,unique=True,db_index=True)

    #paths = models.ManyToManyField(FileItem,related_name='objects')

    def __unicode__(self): 
        return self.identifier 

    class Meta:
        verbose_name = "Tracked Object"
        verbose_name_plural = "Tracked Objects"

#-------------------------------------------------------------------------------

class PathItem(models.Model):
    """ path class - keep the shared the base and the specific relative part
    separate"""

    # EOP allowed mask types 
    FILE=1              # a file without any specific meaning 
    RAWDATA=3           # raw image data 
    METADATA=5          # metadata 
    RAW_AND_METADATA=7  # data and metadata in one file 
    RASTER_MASK=11      # raster mask 
    VECTOR_MASK=13      # vector mask 
    BROWSE=15           # browse image 
    DIRECTORY=128       # directory 

    TYPE_CHOICES = ( 
        ( FILE, "file" ),
        ( RAWDATA, "data" ),
        ( METADATA, "metadata" ),
        ( RAW_AND_METADATA, "data+metadata" ),
        ( RASTER_MASK, "raster-mask" ),
        ( VECTOR_MASK, "vector-mask" ),
        ( BROWSE, "browse" ),
        ( DIRECTORY, "directory" ),
    ) 

    TYPE_STRINGS= tuple( v for k,v in TYPE_CHOICES )

    type = models.PositiveSmallIntegerField( choices=TYPE_CHOICES,
                                            blank=False, null=False ) 

    time_created = models.DateTimeField("Created",auto_now_add=True)
    time_updated = models.DateTimeField("Last update",auto_now=True)

    path  = models.CharField(max_length=1024,unique=False,db_index=True)
    label = models.CharField(max_length=64,blank=True,null=True)

    owner = models.ForeignKey(TrackedObject,related_name="paths")

    class Meta:
        verbose_name = "Path Item"
        verbose_name_plural = "Path Items"

#-------------------------------------------------------------------------------
