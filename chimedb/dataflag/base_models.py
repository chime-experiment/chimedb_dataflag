"""
Base classes for table definitions for the CHIME data flagging (and opinion) tools.
"""
# === Start Python 2/3 compatibility
from __future__ import absolute_import, division, print_function, unicode_literals
from future.builtins import *  # noqa  pylint: disable=W0401, W0614
from future.builtins.disabled import *  # noqa  pylint: disable=W0401, W0614

# === End Python 2/3 compatibility

from chimedb.core.orm import base_model, JSONDictField, EnumField

import logging
import numpy as np
import peewee as pw

_logger = logging.getLogger("chimedb")
_logger.addHandler(logging.NullHandler())


class DataSubsetType(base_model):
    """Base class for types of anything describing data subsets."""

    name = pw.CharField(max_length=64, unique=True)
    description = pw.TextField(null=True)
    metadata = JSONDictField(null=True)
