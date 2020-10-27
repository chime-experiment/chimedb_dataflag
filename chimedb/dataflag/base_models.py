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


class DataSubset(base_model):
    """
    Base class for anything that describes a subset of data.

    Attributes
    ==========
    start_time, finish_time : double
        The start and end times as UNIX times.
    metadata : dict
        A JSON object with extended metadata. See below for guidelines.
    """

    start_time = pw.DoubleField()
    finish_time = pw.DoubleField(null=True)

    metadata = JSONDictField(null=True)

    @property
    def instrument(self):
        """The instrument the flag applies to."""
        if self.metadata is not None:
            return self.metadata.get("instrument", None)
        else:
            return None

    @property
    def freq(self):
        """The list of inputs the flag applies to. `None` if not set."""
        if self.metadata is not None:
            return self.metadata.get("freq", None)
        else:
            return None

    @property
    def freq_mask(self):
        """An array for the frequencies flagged (`True` if the flag applies)."""

        # TODO: hard coded for CHIME
        mask = np.ones(1024, dtype=np.bool)

        if self.freq is not None:
            mask[self.freq] = False
            mask = ~mask

        return mask

    @property
    def inputs(self):
        """The list of inputs the flag applies to. `None` if not set."""
        if self.metadata is not None:
            return self.metadata.get("inputs", None)
        else:
            return None

    @property
    def input_mask(self):
        """An array for the inputs flagged (`True` if the flag applies)."""
        if self.instrument is None:
            return None

        inp_dict = {"chime": 2048, "pathfinder": 256}
        mask = np.ones(inp_dict[self.instrument], dtype=np.bool)

        if self.inputs is not None:
            mask[self.inputs] = False
            mask = ~mask

        return mask


class DataSubsetType(base_model):
    """Base class for types of anything describing data subsets."""

    name = pw.CharField(max_length=64, unique=True)
    description = pw.TextField(null=True)
    metadata = JSONDictField(null=True)
