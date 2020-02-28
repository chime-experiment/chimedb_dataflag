"""
Table definitions for the CHIME data flagging tools
"""
# === Start Python 2/3 compatibility
from __future__ import absolute_import, division, print_function, unicode_literals
from future.builtins import *  # noqa  pylint: disable=W0401, W0614
from future.builtins.disabled import *  # noqa  pylint: disable=W0401, W0614

# === End Python 2/3 compatibility

from chimedb.core.orm import base_model, JSONDictField

import peewee as pw

# Logging
# =======

import logging

_logger = logging.getLogger("chimedb")
_logger.addHandler(logging.NullHandler())


# Tables pertaining to the data flags.
# ====================================


class DataFlagType(base_model):
    """The type of flag that we are using.

    Attributes
    ----------
    name : string
        Name of the type of flag.
    description : string
        A long description of the flag type.
    metadata : dict
        An optional JSON object describing how this flag type is being generated.
    """

    name = pw.CharField(max_length=64)
    description = pw.TextField(null=True)
    metadata = JSONDictField(null=True)


class DataFlag(base_model):
    """A flagged range of data.

    Attributes
    ----------
    type : DataFlagType
        The type of flag.
    start_time, finish_time : double
        The start and end times as UNIX times.
    metadata : dict
        A JSON object with extended metadata. See below for guidelines.

    Notes
    -----
    To ensure that the added metadata is easily parseable, it should adhere
    to a rough schema. The following common fields may be present:

    `instrument` : optional
        The name of the instrument that the flags applies to. If not set,
        assumed to apply to all instruments.
    `freq` : optional
        A list of integer frequency IDs that the flag applies to. If not
        present the flag is assumed to apply to *all* frequencies.
    `inputs` : optional
        A list of integer feed IDs (in cylinder order) that the flag applies
        to. If not present the flag is assumed to apply to *all* inputs. For
        this to make sense an `instrument` field is also required.

    Any other useful metadata can be put straight into the metadata field,
    though it must be accessed directly.
    """

    type = pw.ForeignKeyField(DataFlagType, backref="flags")

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
        """The list of inputs the flag applies to. `None` if not set.
        """
        if self.metadata is not None:
            return self.metadata.get("freq", None)
        else:
            return None

    @property
    def freq_mask(self):
        """An array for the frequencies flagged (`True` if the flag applies).
        """

        # TODO: hard coded for CHIME
        mask = np.ones(1024, dtype=np.bool)

        if self.freq is not None:
            mask[self.freq] = False
            mask = ~mask

        return mask

    @property
    def inputs(self):
        """The list of inputs the flag applies to. `None` if not set.
        """
        if self.metadata is not None:
            return self.metadata.get("inputs", None)
        else:
            return None

    @property
    def input_mask(self):
        """An array for the inputs flagged (`True` if the flag applies).
        """
        if self.instrument is None:
            return None

        inp_dict = {"chime": 2048, "pathfinder": 256}
        mask = np.ones(inp_dict[self.instrument], dtype=np.bool)

        if self.inputs is not None:
            mask[self.inputs] = False
            mask = ~mask

        return mask

    @classmethod
    def create_flag(
        cls,
        flagtype,
        start_time,
        finish_time,
        freq=None,
        instrument="chime",
        inputs=None,
        metadata=None,
    ):
        """Create a flag entry.

        Parameters
        ----------
        flagtype : string
            Name of flag type. Must already exist in database.
        start_time, end_time : float
            Start and end of flagged time.
        freq : list, optional
            List of affected frequencies.
        instrument : string, optional
            Affected instrument.
        inputs : list, optional
            List of affected inputs.
        metadata : dict
            Extra metadata to go with the flag entry.

        Returns
        -------
        flag : PipelineFlag
            The flag instance.
        """

        table_metadata = {}

        if freq is not None:
            if not isinstance(freq, list):
                raise ValueError("freq argument (%s) must be list.", freq)
            table_metadata["freq"] = freq

        if instrument is not None:
            table_metadata["instrument"] = instrument

        if inputs is not None:
            if not isinstance(inputs, list):
                raise ValueError("inputs argument (%s) must be list.", inputs)
            table_metadata["inputs"] = inputs

        if metadata is not None:
            if not isinstance(metadata, dict):
                raise ValueError("metadata argument (%s) must be dict.", metadata)
            table_metadata.update(metadata)

        # Get the flag
        type_ = DataFlagType.get(name=flagtype)

        flag = cls.create(
            type=type_,
            start_time=start_time,
            finish_time=finish_time,
            metadata=table_metadata,
        )

        return flag
