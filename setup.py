# === Start Python 2/3 compatibility
from __future__ import absolute_import, division, print_function
from future.builtins import *  # noqa  pylint: disable=W0401, W0614
from future.builtins.disabled import *  # noqa  pylint: disable=W0401, W0614

# === End Python 2/3 compatibility

from setuptools import setup

import codecs
import os
import re
import versioneer


setup(
    name="chimedb.dataflag",
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    packages=["chimedb.dataflag"],
    zip_safe=False,
    install_requires=[
        "chimedb @ git+https://github.com/chime-experiment/chimedb.git",
        "ch_util @ git+ssh://git@github.com/chime-experiment/ch_util.git@master",
        "peewee >= 3.10",
        "future",
        "Click",
        "ansimarkup",
        "tabulate",
        "PyYAML",
        "arrow",
    ],
    entry_points="""
        [console_scripts]
        cdf=chimedb.dataflag.client:cli
    """,
    author="CHIME collaboration",
    author_email="richard@phas.ubc.ca",
    description="CHIME data flag tools",
    license="MIT",
    url="https://github.org/chime-experiment/chimedb_dataflag",
)
