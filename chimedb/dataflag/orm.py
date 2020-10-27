"""
Table definitions for the CHIME data flagging (and opinion) tools
"""
# === Start Python 2/3 compatibility
from __future__ import absolute_import, division, print_function, unicode_literals
from future.builtins import *  # noqa  pylint: disable=W0401, W0614
from future.builtins.disabled import *  # noqa  pylint: disable=W0401, W0614

# === End Python 2/3 compatibility

from .base_models import DataSubset, DataSubsetType

from chimedb.core.orm import base_model, JSONDictField, EnumField
from chimedb.core.exceptions import ValidationError
from chimedb.core.mediawiki import MediaWikiUser

import peewee as pw

# Logging
# =======

import logging

_logger = logging.getLogger("chimedb")
_logger.addHandler(logging.NullHandler())


# Tables pertaining to the data flags.
# ====================================


class DataRevision(base_model):
    """
    Revision of offline pipeline that produced the data.
    """

    name = pw.CharField(max_length=32, unique=True)
    description = pw.TextField(null=True)


class DataFlagClient(base_model):
    """Client used to create a data flag.

    Attributes
    ----------
    client_name : str
        Name of the client software.
    client_version : str
        Version string.
    """

    client_name = pw.CharField()
    client_version = pw.CharField()


class DataFlagType(DataSubsetType):
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

    pass


class DataFlag(DataSubset):
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


# Tables pertaining to the data flag opinions.
# ============================================


class DataFlagVote(base_model):
    """
    A Vote that resulted in the translation of opinions to flags.

    Attributes
    ----------
    time : float
        Unix time at vote creation.
    mode : str
        Voting mode name. They are implemented in `chimed.dataflag.opinion.vote`.
    client : DataFlagClient
        Client used to vote.
    """

    max_len_mode_name = 32

    time = pw.FloatField()
    mode = pw.CharField(max_length=max_len_mode_name)
    client = pw.ForeignKeyField(DataFlagClient)
    revision = pw.ForeignKeyField(DataRevision, backref="votes")
    flag = pw.ForeignKeyField(DataFlag, backref="vote")


class DataFlagOpinionType(DataSubsetType):
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


class DataFlagOpinion(DataSubset):
    """A persons opinion on flagging a range of data.

    Attributes
    ----------
    type : DataFlagOpinionType
        The type of flag.
    user : MediaWikiUser
        The user who made this opinion.
    decision : str
        Decision about the data: "good", "bad" or "unsure".
    start_time, finish_time : double
        The start and end times as UNIX times.
    metadata : dict
        A JSON object with extended metadata. See below for guidelines.
    creation_time, last_edit : double
        The time of creation and last edit as UNIX times.
    revision : str
        Name of data revision this opinion based on.

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
    decision = EnumField(["good", "bad", "unsure"])

    creation_time = pw.DoubleField()
    last_edit = pw.DoubleField()
    client = pw.ForeignKeyField(DataFlagClient)
    revision = pw.ForeignKeyField(DataRevision, backref="opinions")

    class Meta:
        indexes = (
            # create a unique index
            (("type", "user", "start_time", "finish_time", "revision"), True),
        )

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
        revision,
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
        revision : str
            Name of data revision this opinion based on.

        Returns
        -------
        opinion : DataFlagOpinion
            The opinion instance.
        """

        if not isinstance(decision, str) or decision not in cls.decision.enum_list:
            raise ValidationError(
                "Invalid value '%s' for 'decision'. Choose one of %s"
                % (decision, cls.decision.enum_list)
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

        # Get the revision
        revision = DataRevision.get(name=revision)

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
            revision=revision,
        )

        return opinion


class DataFlagVoteOpinion(base_model):
    """Many-to-many relationship between votes and opinions."""

    vote = pw.ForeignKeyField(DataFlagVote)
    opinion = pw.ForeignKeyField(DataFlagOpinion)
