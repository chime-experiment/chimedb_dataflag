"""
Table definitions for the CHIME data flag opinions.
"""
# === Start Python 2/3 compatibility
from __future__ import absolute_import, division, print_function, unicode_literals
from future.builtins import *  # noqa  pylint: disable=W0401, W0614
from future.builtins.disabled import *  # noqa  pylint: disable=W0401, W0614

# === End Python 2/3 compatibility

from .. import DataFlag, DataFlagType

from chimedb.core.orm import base_model, JSONDictField
from chimedb.core.exceptions import ValidationError
from chimedb.core import MediaWikiUser

import peewee as pw

# Logging
# =======

import logging

_logger = logging.getLogger(__name__)
_logger.addHandler(logging.NullHandler())


# Tables pertaining to the data flag opinions.
# ============================================


class DataFlagClient(base_model):
    client_name = pw.CharField()
    client_version = pw.CharField()


class DataFlagOpinionType(DataFlagType):
    """The type of opinion that we are using.

    Attributes
    ----------
    name : string
        Name of the type of opinion.
    description : string
        A long description of the opinion type.
    metadata : dict
        An optional JSON object describing how this opinion type is being generated.
    """

    pass


class DataFlagOpinion(DataFlag):
    """A persons opinion on flagging a range of data.

    Attributes
    ----------
    type : DataFlagOpinionType
        The type of flag.
    user : MediaWikiUser
        The user who made this opinion.
    decision : str
        Decision about the daa: "good", "bad" or "unsure".
    start_time, finish_time : double
        The start and end times as UNIX times.
    metadata : dict
        A JSON object with extended metadata. See below for guidelines.
    creation_time, last_edit : double
        The time of creation and last edit as UNIX times.

    Notes
    -----
    To ensure that the added metadata is easily parseable, it should adhere
    to a rough schema. The following common fields may be present:

    `instrument` : optional
        The name of the instrument that the flag opinion applies to. If not set,
        assumed to apply to all instruments.
    `freq` : optional
        A list of integer frequency IDs that the flag opinion applies to. If not
        present the flagging opinion is assumed to apply to *all* frequencies.
    `inputs` : optional
        A list of integer feed IDs (in cylinder order) that the flagging opinion applies
        to. If not present the flagging opinion is assumed to apply to *all* inputs. For
        this to make sense an `instrument` field is also required.

    Any other useful metadata can be put straight into the metadata field,
    though it must be accessed directly.
    """

    type = pw.ForeignKeyField(DataFlagOpinionType, backref="opinions")
    user = pw.ForeignKeyField(MediaWikiUser, backref="opinions")
    choices_decision = ["good", "bad", "unsure"]
    decision = pw.CharField(max_length=max([len(c) for c in choices_decision]))
    creation_time = pw.DoubleField()
    last_edit = pw.DoubleField()
    client = pw.ForeignKeyField(DataFlagClient)

    @classmethod
    def create_opinion(
        cls,
        username,
        creation_time,
        decision,
        opiniontype,
        client_name,
        client_version,
        start_time,
        finish_time,
        freq=None,
        instrument="chime",
        inputs=None,
        metadata=None,
    ):
        """Create a flagging opinion entry.

        Parameters
        ----------
        decision : str
            "good", "bad" or "unsure".
        opiniontype : str
            Name of opinion type. Must already exist in database.
        start_time, finish_time : float
            Start and end of flagged time.
        username : str
            Name of the user entering the opinion.
        creation_time : double
            Unix time when the opinion was entered. Default: current time.
        freq : list, optional
            List of affected frequencies.
        instrument : str, optional
            Affected instrument.
        inputs : list, optional
            List of affected inputs.
        metadata : dict
            Extra metadata to go with the opinion entry.

        Returns
        -------
        opinion : DataFlagOpinion
            The opinion instance.
        """

        if not isinstance(decision, str) or decision not in cls.choices_decision:
            raise ValidationError(
                "Invalid value '%s' for 'decision'. Choose one of %s"
                % (decision, cls.choices_decision)
            )

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
        type_ = DataFlagOpinionType.get(name=opiniontype)

        # Get the user
        username = username[0].upper() + username[1:]
        user_ = MediaWikiUser.get(user_name=username)

        # Get the client
        client, _ = DataFlagClient.get_or_create(
            client_name=client_name, client_version=client_version
        )

        opinion = cls.create(
            user=user_,
            creation_time=creation_time,
            last_edit=creation_time,
            decision=decision,
            type=type_,
            client=client,
            start_time=start_time,
            finish_time=finish_time,
            metadata=table_metadata,
        )

        return opinion


class DataFlagVote(base_model):
    max_len_mode_name = 32

    time = pw.FloatField()
    mode = pw.CharField(max_length=max_len_mode_name)
    client = pw.ForeignKeyField(DataFlagClient)
    resulting_flag = pw.ForeignKeyField(DataFlag, backref="vote", null=True)


class DataFlagVoteOpinion(base_model):
    """Many-to-many relationship between votes and opinions."""

    vote = pw.ForeignKeyField(DataFlagVote)
    opinion = pw.ForeignKeyField(DataFlagOpinion)
