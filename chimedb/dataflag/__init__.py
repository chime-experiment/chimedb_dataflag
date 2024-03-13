"""
CHIME Data Flag and Opinion - Database Package

Opinion Database Model Classes
==============================

* DataFlagClient
    The client (software) used to create a dataflag. This could for example be
    `chimedb.dataflag.client.py` or `bondia`. The client is described by a name and version.

* DataFlagOpinionType
    A type for dataflag opinions. This should explain how they are created: manually, through a
    web interface (like bondia), etc.

* DataFlagOpinion
    Instead of directly creating data flags and adding them to the database, users can add their
    opinions on flagging subsets of data. User opinions can later get translated to flags.

* DataFlagVote
    A vote is the action that translates a set of existing user opinions to one data flag.
    The voting mode name is stored here. Voting modes are implemented in `VotingJudge`.

* DataFlagVoteOpinion
    Many-to-many relationship between votes and opinions.

* DataRevision
    The revision of the offline pipeline that created the data that opinions and votes are based
    on. An opinion is always strictly based on the revision of the offline pipeline that produced
    the data the user looked at to make a decision. A vote is still based on a revision, but may
    include opinions from other revisions (depending on the voting mode).

Voting
======

* VotingJudge
    Can translate from opinions to flags when run.
"""

from .orm import (
    DataFlagClient,
    DataFlagOpinionType,
    DataFlagOpinion,
    DataFlagVote,
    DataFlagVoteOpinion,
    DataRevision,
    DataFlagType,
    DataFlag,
)

from . import _version

__version__ = _version.get_versions()["version"]

from .vote import VotingJudge
