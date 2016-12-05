#!/usr/bin/env python2.7

from setuptools import setup
import os

setup(
    name = "pyisy",
    version = "1.0",
    author = "Carl Seelye",
    author_email = "cseelye@gmail.com",
    description = "Python API for Universal Devices ISY994 Insteon controller",
    license = "MIT",
    keywords = "isy udi insteon",
    packages = ["pyisy"],
    url = "https://github.com/cseelye/pyisy",
    long_description = open(os.path.join(os.path.dirname(__file__), "README.rst")).read(),
    install_requires = [
        "requests",
        "xmltodict",
    ]
)
