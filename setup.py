#-------------------------------------------------------------------------------
#
# Project: EOxServer <http://eoxserver.org>
# Authors: Stephan Krause <stephan.krause@eox.at>
#          Stephan Meissl <stephan.meissl@eox.at>
#          Fabian Schindler <fabian.schindler@eox.at>
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

import os, sys

# Hack to remove setuptools "feature" which resulted in
# ignoring MANIFEST.in when code is in an svn repository.
# TODO find a nicer solution
import subprocess
from setuptools.command import sdist
from distutils.extension import Extension
del sdist.finders[:]

from setuptools import setup

from eoxserver import get_version

version = get_version()

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

def fullsplit(path, result=None):
    """
    Split a pathname into components (the opposite of os.path.join) in a
    platform-neutral way.
    """
    if result is None:
        result = []
    head, tail = os.path.split(path)
    if head == '':
        return [tail] + result
    if head == path:
        return result
    return fullsplit(head, [tail] + result)

def get_gdal_libs(default=None):
    if default is None:
        default = ("", "")
    
    p = subprocess.Popen(["gdal-config", "--libs"], stdout=subprocess.PIPE)
    if p.wait() != 0:
        return default
    output = p.stdout.read().strip().split(" ")
    lib = ""
    libdir = ""
    for part in output:
        if part.startswith("-L"):
            libdir = part[2:]
        elif part.startswith("-l"):
            lib = part[2:]

    return libdir, lib

def get_gdal_incdirs(default=None):
    if default is None:
        default = ("", "")
    
    p = subprocess.Popen(["gdal-config", "--cflags"], stdout=subprocess.PIPE)
    if p.wait() != 0:
        return default
    output = p.stdout.read().strip().split(" ")
    lib = ""
    libdir = ""
    for part in output:
        if part.startswith("-I"):
            incdir = part[2:]

    return incdir

packages, data_files = [], []
for dirpath, dirnames, filenames in os.walk('eoxserver'):
    for i, dirname in enumerate(dirnames):
        if dirname.startswith('.'): del dirnames[i]
    if '__init__.py' in filenames:
        packages.append('.'.join(fullsplit(dirpath)))
    elif filenames:
        data_files.append([dirpath, [os.path.join(dirpath, f) for f in filenames]])

# On readthecods.org we don't want the reftools to be build
on_rtd = os.environ.get('READTHEDOCS', None) == 'True'
if on_rtd:
    ext_modules = []
else:
    gdal_libdir, gdal_lib = get_gdal_libs()
    gdal_incdir = get_gdal_incdirs()

    ext_modules = [
        Extension(
            'eoxserver.processing.gdal._reftools',
            sources=['eoxserver/processing/gdal/reftools.c'],
            libraries=[gdal_lib],
            library_dirs=[gdal_libdir],
            include_dirs=[gdal_incdir],
        ),
        Extension(
            'eoxserver.processing.gdal._reftools_ext',
            sources=['eoxserver/processing/gdal/reftools.c'],
            libraries=[gdal_lib],
            library_dirs=[gdal_libdir],
            include_dirs=[gdal_incdir],
            define_macros = [('USE_GDAL_EOX_EXTENSIONS', '1')],
        )
    ]

    # Check if we should build the extended reftools relying on gdal-eox
    if "--disable-extended-reftools" in sys.argv:
        ext_modules.pop()
        sys.argv.remove("--disable-extended-reftools")

setup(
    name='EOxServer_dream',
    version=version.replace(' ', '-'),
    packages=packages,
    data_files=data_files,
    include_package_data=True,
    scripts=[
        "eoxserver/scripts/eoxserver-admin.py",
        "tools/eoxserver-atpd.py",
        "tools/eoxserver-validate_xml.py",
        "tools/eoxserver-preprocess.py"
    ],
    ext_modules=ext_modules,
    install_requires=[
        'django>=1.4',
    ],
    zip_safe = False,
    
    # Metadata
    author="EOX IT Services GmbH",
    author_email="office@eox.at",
    maintainer="EOX IT Services GmbH",
    maintainer_email="packages@eox.at",
    
    description="EOxServer is a server for Earth Observation (EO) data",
    long_description=read("README.rst"),
    
    classifiers=[
          'Development Status :: 3 - Alpha',
          'Environment :: Console',
          'Environment :: Web Environment',
          'Framework :: Django',
          'Intended Audience :: End Users/Desktop',
          'Intended Audience :: Other Audience',
          'Intended Audience :: System Administrators',
          'Intended Audience :: Science/Research',
          'License :: OSI Approved :: MIT License',
          'Natural Language :: English',
          'Operating System :: OS Independent',
          'Programming Language :: Python',
          'Programming Language :: Python :: 2.5',
          'Programming Language :: Python :: 2.6',
          'Programming Language :: Python :: 2.7',
          'Topic :: Database',
          'Topic :: Internet',
          'Topic :: Internet :: WWW/HTTP',
          'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
          'Topic :: Multimedia :: Graphics',
          'Topic :: Scientific/Engineering :: GIS',
          'Topic :: Scientific/Engineering :: Information Analysis',
          'Topic :: Scientific/Engineering :: Visualization',
    ],
    
    license="EOxServer Open License (MIT-style)",
    keywords="Earth Observation, EO, OGC, WCS, WMS",
    url="http://eoxserver.org/"
)
