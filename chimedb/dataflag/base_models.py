"""
Base classes for table definitions for the CHIME data flagging (and opinion) tools.
"""

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
