#-------------------------------------------------------------------------------
# $Id$
#
# Project: EOxServer <http://eoxserver.org>
# Authors: Stephan Krause <stephan.krause@eox.at>
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

from tempfile import mkstemp
import ctypes as C
import os.path
import logging

from osgeo import gdal

from eoxserver.core.util.bbox import BBox
from eoxserver.core.exceptions import InternalError

ERROR_LABEL = "Referenceable grid handling is disabled!" \
              " Did you compile the 'reftools' C module?!"

class RECT(C.Structure):
    _fields_ = [("x_off", C.c_int),
                ("y_off", C.c_int),
                ("x_size", C.c_int),
                ("y_size", C.c_int)]

class SUBSET(C.Structure):
    _fields_ = [("srid", C.c_int),
                ("minx", C.c_double),
                ("miny", C.c_double),
                ("maxx", C.c_double),
                ("maxy", C.c_double)]

_lib_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "_reftools.so"
)

global REFTOOLS_USEABLE
    
try:
    _lib = C.LibraryLoader(C.CDLL).LoadLibrary(_lib_path)

    _get_footprint_wkt = _lib.eoxs_get_footprint_wkt
    _get_footprint_wkt.argtypes = [C.c_void_p]
    _get_footprint_wkt.restype = C.POINTER(C.c_char)

    _rect_from_subset = _lib.eoxs_rect_from_subset
    _rect_from_subset.argtypes = [C.c_void_p, C.POINTER(SUBSET)]
    _rect_from_subset.restype = C.POINTER(RECT)

    _create_rectified_vrt = _lib.eoxs_create_rectified_vrt
    _create_rectified_vrt.argtypes = [C.c_void_p, C.c_char_p, C.c_int]
    _create_rectified_vrt.restype = C.c_int

    _free_string = _lib.eoxs_free_string
    _free_string.argtypes = [C.c_char_p]

    REFTOOLS_USABLE = True
except:
    logging.warn("Could not load '%s'. Referenceable Datasets will not be usable." % _lib_path)
    
    REFTOOLS_USABLE = False


def _open_ds(path_or_ds):
    if isinstance(path_or_ds, gdal.Dataset):
        return path_or_ds
    gdal.AllRegister()
    return gdal.Open(str(path_or_ds))


def get_footprint_wkt(path_or_ds):
    if not REFTOOLS_USABLE:
        raise InternalError(ERROR_LABEL)
    
    ds = _open_ds(path_or_ds)
    
    ret = _get_footprint_wkt(C.c_void_p(long(ds.this)))
    string = C.cast(ret, C.c_char_p).value
    
    _free_string(ret)
    return string

def rect_from_subset(path_or_ds, srid, minx, miny, maxx, maxy):
    if not REFTOOLS_USABLE:
        raise InternalError(ERROR_LABEL)

    ds = _open_ds(path_or_ds)
    
    rect = RECT()
    ret = _rect_from_subset(
        C.c_void_p(long(ds.this)),
        C.byref(SUBSET(srid, minx, miny, maxx, maxy)),
        C.byref(rect)
    )
    if not ret:
        return None
    
    #return (rect.x_off, rect.y_off, rect.x_size, rect.y_size)
    return BBox(rect.x_size, rect.y_size, rect.x_off, rect.y_off)

def create_rectified_vrt(path_or_ds, vrt_path, srid=None):
    if not REFTOOLS_USABLE:
        raise InternalError(ERROR_LABEL)

    ds = _open_ds(path_or_ds)
    ptr = C.c_void_p(long(ds.this))

    if srid:
        ret = _create_rectified_vrt(ptr, vrt_path, srid)
    else:
        ret = _create_rectified_vrt(ptr, vrt_path, 0)  
    
    if not ret:
        raise InternalError(
            "Could not create rectified VRT."
        )

def create_temporary_vrt(path_or_ds, srid=None):
    if not REFTOOLS_USABLE:
        raise InternalError(ERROR_LABEL)

    from eoxserver.core.system import System
    _, vrt_path = mkstemp(
        dir = System.getConfig().getConfigValue("processing.gdal.reftools", "vrt_tmp_dir"),
        suffix = ".vrt"
    )
    
    create_rectified_vrt(path_or_ds, vrt_path, srid)
    
    return vrt_path
