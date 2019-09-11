# === Start Python 2/3 compatibility
from __future__ import absolute_import, division, print_function
from future.builtins import *  # noqa  pylint: disable=W0401, W0614
from future.builtins.disabled import *  # noqa  pylint: disable=W0401, W0614

# === End Python 2/3 compatibility

from setuptools import setup

import codecs
import os
import re


# Get the version from __init__.py without having to import it.
def _get_version():
    with codecs.open(
        os.path.join(
            os.path.abspath(os.path.dirname(__file__)),
            "chimedb",
            "dataflag",
            "__init__.py",
        ),
        "r",
    ) as init_py:
        version_match = re.search(
            r"^__version__ = ['\"]([^'\"]*)['\"]", init_py.read(), re.M
        )

        if version_match:
            return version_match.group(1)
        raise RuntimeError("Unable to find version string.")


setup(
    name="chimedb.dataflag",
    version=_get_version(),
    packages=["chimedb.dataflag"],
    zip_safe=False,
    install_requires=[
        "chimedb @ git+ssh://git@github.com/chime-experiment/chimedb.git",
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
