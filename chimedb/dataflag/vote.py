"""
CHIME Dataflag Voting module.

After user opinions are inserted, a vote can be made to translate opinions to data flags.

To add voting modes, create a vote method in the class `VotingJudge` and name it in
`VotingJudge._modes`.
"""

import arrow
import peewee as pw

from ch_util.ephemeris import csd_to_unix

from .orm import (
    DataFlagVote,
    DataFlagOpinion,
    DataFlag,
    DataFlagClient,
    DataFlagVoteOpinion,
    DataRevision,
)
from . import __version__


class VotingJudge:
    """
    Translate opinions to data flags.

    Parameters
    ----------
    mode : str
        Name of the voting mode to use.

    Attributes
    ----------
    mode_choices : List(str)
        Names of available voting modes.
    """

    # the max time we think a vote could take
    max_vote_time = 60

    def hypnotoad_vote(self, timestamp):
        """Hypnotoad voting mode.

        Only accepts unanimous decisions, i.e. a single user can be the hypnotoad. But as soon as
        there is one opposing vote, no flag is created.
        """
        # get time of last vote
        last_vote_time = DataFlagVote.select(pw.fn.MAX(DataFlagVote.time)).scalar()

        # substract a bit to exclude late votes that were not counted
        if last_vote_time:
            last_vote_time -= self.max_vote_time
        else:
            last_vote_time = 0

        # Get all opinions entered since then
        new_opinions = DataFlagOpinion.select().where(
            (DataFlagOpinion.last_edit >= last_vote_time)
            & (DataFlagOpinion.revision == self.revision)
        )

        flags = []
        for opinion in new_opinions:
            # Check if there is another opinion for the same time that disagrees
            more_opinions = (
                DataFlagOpinion.select()
                .where(
                    DataFlagOpinion.decision != opinion.decision
                    and DataFlagOpinion.lsd == opinion.lsd
                )
                .count()
            )

            if not more_opinions:
                # ALL GLORY TO THE HYPNOTOAD
                flag = self._translate_single_opinion(opinion, timestamp)
                flags.append(flag)
        return flags

    def _translate_single_opinion(self, opinion, timestamp):
        flag = None
        if opinion.decision == "bad":
            # Translate from opinions LSD to flags start- and finish-time.
            start_time = csd_to_unix(opinion.lsd)
            finish_time = csd_to_unix(opinion.lsd + 1)

            flag = DataFlag.create_flag(
                "vote",
                start_time,
                finish_time,
                opinion.freq,
                opinion.instrument,
                opinion.inputs,
            )
        client, _ = DataFlagClient.get_or_create(
            client_name=__name__, client_version=__version__
        )
        vote = DataFlagVote.create(
            time=timestamp,
            mode=self.mode,
            client=client,
            flag=flag,
            revision=self.revision,
            lsd=opinion.lsd,
        )
        DataFlagVoteOpinion.create(vote=vote, opinion=opinion)
        return flag

    # Map from mode name to method name.
    # Don't make a mode name longer than 32 characters.
    _modes = {"hypnotoad": hypnotoad_vote}
    mode_choices = list(_modes.keys())

    def __init__(self, mode, revision):
        if len(mode) > DataFlagVote.max_len_mode_name:
            raise RuntimeError(
                "Mode can't be longer than %i characters (len(%s) is %i)."
                % (DataFlagVote.max_len_mode_name, mode, len(mode))
            )

        if mode not in self.mode_choices:
            raise UserWarning(
                "Invalid value for 'mode' (choose on of %s)." % self.mode_choices
            )

        try:
            self.vote = lambda: self._modes[mode](self, arrow.utcnow().timestamp)
        except KeyError:
            raise ValueError("Invalid mode: %s" % mode)

        self.mode = mode
        if isinstance(revision, str):
            self.revision = DataRevision.get(name=revision)
        elif isinstance(revision, DataRevision):
            self.revision = revision
        else:
            raise TypeError(
                "Expected type str or DataRevision for argument revision (got %s)."
                % type(revision)
            )
