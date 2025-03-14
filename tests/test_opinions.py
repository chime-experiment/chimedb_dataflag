import arrow
from click.testing import CliRunner
import logging
import tempfile
import os
import pytest
import time

import chimedb.core as db

from chimedb.dataflag.client import (
    opinion_type_list,
    create_opinion_type,
    create_type,
    show_opinion_type,
    create_opinion,
    opinion_list,
    opinion_show,
    opinion_edit,
    opinion_vote,
    create_revision,
    revision_list,
    show_revision,
)
from chimedb.dataflag import (
    DataFlagOpinionType,
    DataFlagOpinion,
    DataRevision,
)


user = "Test"

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("chimedb")
logger.setLevel("DEBUG")


@pytest.fixture
def db_conn():
    """Set up chimedb.core for testing with a local dummy DB."""
    (fd, rcfile) = tempfile.mkstemp(text=True)
    with os.fdopen(fd, "a") as rc:
        rc.write(
            """\
        chimedb:
            db_type:         MySQL
            db:              test
            user_ro:         test
            passwd_ro:       test
            user_rw:         test
            passwd_rw:       test
            host:            127.0.0.1
            port:            32574
        """
        )

    # Tell chimedb where the database connection config is
    assert os.path.isfile(rcfile), "Could not find {}.".format(rcfile)
    os.environ["CHIMEDB_TEST_RC"] = rcfile

    # Make sure we don't write to the actual chime database
    os.environ["CHIMEDB_TEST_ENABLE"] = "Yes, please."

    db.connect()
    db.orm.create_tables(["chimedb.dataflag.opinion"])

    # insert a user with password ******
    pwd = ":B:0000ffff:e989651ffffcb5bf9b9abedfdab58460"
    db.mediawiki.MediaWikiUser.get_or_create(user_name=user, user_password=pwd)


@pytest.fixture
def test_create_opinions(db_conn):
    # Create opinion type
    type_, _ = DataFlagOpinionType.get_or_create(
        name="test", description="blubb", metadata={"version": 0}
    )

    # Create revision
    revision, _ = DataRevision.get_or_create(name="test", description="foo")

    with pytest.raises(db.exceptions.ValidationError):
        DataFlagOpinion.create_opinion(
            user,
            time.time(),
            True,
            type_.name,
            "test",
            "0.0.0",
            "2111",
            revision=revision.name,
        )

    with pytest.raises(db.exceptions.ValidationError):
        DataFlagOpinion.create_opinion(
            user,
            time.time(),
            "idontknow",
            type_.name,
            "test",
            "0.0.0",
            "2111",
            revision=revision.name,
        )

    return DataFlagOpinion.create_opinion(
        user,
        time.time(),
        "bad",
        type_.name,
        "test",
        "0.0.0",
        "2111",
        revision=revision.name,
        notes="I really don't know!",
    )


def test_click(test_create_opinions):
    runner = CliRunner()
    runner.invoke(create_opinion_type, ["test2", "--description", "bla", "--force"])

    result = runner.invoke(opinion_type_list)
    assert result.exit_code == 0, result.output
    assert result.output == "test\ntest2\n"

    result = runner.invoke(show_opinion_type, ["test"])
    assert result.exit_code == 0, result.output
    assert "type: test" in result.output
    assert "version: 0" in result.output

    result = runner.invoke(
        create_revision,
        ["testtest", "--force"],
    )
    assert result.exit_code == 0, result.output

    result = runner.invoke(
        create_revision,
        ["testtesttest", "--description", "Revision created for testing.", "--force"],
    )
    assert result.exit_code == 0, result.output

    result = runner.invoke(revision_list)
    assert result.exit_code == 0, result.output
    assert "testtesttest" in result.output

    result = runner.invoke(show_revision, "testtesttest")
    assert result.exit_code == 0, result.output
    assert "created for testing" in result.output

    result = runner.invoke(
        create_opinion,
        ["test", "2112", "idontknow", "-u", user, "-r", "test", "--force"],
    )
    assert "Invalid value" in result.output

    result = runner.invoke(
        create_opinion,
        ["test", "2112", "good", "-u", user, "-r" "test", "--force"],
    )
    assert result.exit_code == 0, result.output

    result = runner.invoke(opinion_list)
    assert "test" in result.output
    assert "user" in result.output
    assert "good" in result.output
    assert "bad" in result.output

    result = runner.invoke(opinion_show, ["0"])
    assert "Invalid value" in result.output

    def parse_opinion(result):
        times = [0, 0]
        for val in result.splitlines():
            if val.startswith("creation_time:"):
                times[0] = val[15:]
            elif val.startswith("last_edit:"):
                times[1] = val[11:]
        return times

    result = runner.invoke(opinion_show, [str(test_create_opinions.id)])
    assert result.exit_code == 0, result.output
    assert "user: %s" % user in result.output
    assert "decision: bad" in result.output
    times = parse_opinion(result.output)
    assert times[0] == times[1]

    time.sleep(1)
    new_user = "iknowbetter"
    result = runner.invoke(
        opinion_edit,
        [
            str(test_create_opinions.id),
            "--decision",
            "good",
            "--user",
            new_user,
            "--force",
        ],
    )
    assert result.exit_code != 0, result.output

    result = runner.invoke(
        opinion_edit,
        [
            str(test_create_opinions.id),
            "--decision",
            "good",
            "--force",
        ],
    )
    assert result.exit_code == 0, result.output

    time.sleep(1)
    result = runner.invoke(opinion_show, [str(test_create_opinions.id)])
    assert result.exit_code == 0, result.output
    assert "user: %s" % user in result.output
    assert "decision: good" in result.output
    times = parse_opinion(result.output)
    assert arrow.get(times[1]).is_between(arrow.get(times[0]), arrow.utcnow())

    # create new flagging type: vote
    result = runner.invoke(create_type, ["vote", "-f"])
    assert result.exit_code == 0, result.output

    # vote
    result = runner.invoke(opinion_vote, ["-v", "-m", "hypnotoad", "-r", "test"])
    assert result.exit_code == 0, result.output
