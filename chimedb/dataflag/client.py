import json
import re
import ast
import os
import pwd

import click
import arrow
import tabulate
import yaml
import peewee as pw
import ansimarkup

from chimedb.dataflag import orm, __version__
from chimedb.dataflag.vote import VotingJudge

import chimedb.core as db


# Custom parameter types for click arguments
# ==========================================
class OType(click.ParamType):
    """Opinion type parameter for click."""

    name = "opinion type"

    def convert(self, value, param, ctx):

        _typedict = {dt.name: dt for dt in orm.DataFlagOpinionType.select()}

        if value not in _typedict:
            self.fail(
                'opinion type "%s" unknown. See `cdf opinion_type list` for valid options.'
                % value
            )

        return _typedict[value]


class FType(click.ParamType):
    """Flag type parameter for click."""

    name = "flag type"

    def convert(self, value, param, ctx):

        _typedict = {dt.name: dt for dt in orm.DataFlagType.select()}

        if value not in _typedict:
            self.fail(
                'flag type "%s" unknown. See `cdf type list` for valid options.' % value
            )

        return _typedict[value]


class Flag(click.ParamType):
    """Flag parameter for click."""

    name = "flag"

    def convert(self, value, param, ctx):

        try:
            f = orm.DataFlag.get(id=value)
        except pw.DoesNotExist:
            self.fail(
                'flag id "%i" unknown. See `cdf flag list` ' "for valid ids." % value
            )

        return f


class Opinion(click.ParamType):
    """Opinion parameter for click."""

    name = "opinion"

    def convert(self, value, param, ctx):

        try:
            f = orm.DataFlagOpinion.get(id=value)
        except pw.DoesNotExist:
            self.fail(
                'opinion id "%s" unknown. See `cdf opinion list` '
                "for valid ids." % value
            )

        return f


class Revision(click.ParamType):
    """Revision parameter for click."""

    name = "revision"

    def convert(self, value, param, ctx):

        try:
            f = orm.DataRevision.get(name=value)
        except pw.DoesNotExist:
            self.fail(
                'revision with name "%s" unknown. See `cdf revision list` '
                "for valid revisions." % value
            )

        return f


class Time(click.ParamType):
    """Time parameter for click. Supports any format that arrow can parse."""

    name = "time"

    def __init__(self, allow_null=False):
        super().__init__()
        self.allow_null = allow_null

    def convert(self, value, param, ctx):

        null_values = ["null", "Null", "none", "None"]

        if value in null_values:
            if self.allow_null:
                # Return the string null here as we need to know whether an
                # argument was not supplied (i.e. None), or whether it was set
                # to be missing
                return "null"
            else:
                self.fail("A null time is not allowed.")

        try:
            return arrow.get(value)
        except arrow.parser.ParserError as e:
            self.fail('Could not parse time "%s": %s' % (value, e))


class ListOfType(click.ParamType):
    """Time parameter for click. Supports any format that arrow can parse."""

    def __init__(self, name, type_):
        self.name = name
        self.type = type_

    def convert(self, value, param, ctx):

        try:
            l = ast.literal_eval(value)
        except (SyntaxError, ValueError):
            self.fail('Could not parse "%s" into list.' % value)

        if not isinstance(l, list):
            self.fail('Could not parse "%s" into list.' % value)

        if not all([isinstance(x, self.type) for x in l]):
            self.fail('Not all values were of type "%s"' % repr(self.type))

        return l


class JsonDictType(click.ParamType):
    """Time parameter for click. Supports any format that arrow can parse."""

    name = "jsondict"

    def convert(self, value, param, ctx):

        try:
            d = json.loads(value)
        except json.decoder.JSONDecodeError:
            self.fail('Could not read "%s" as JSON' % value)

        if not isinstance(d, dict):
            self.fail('Could not read JSON "%s" as dict.' % value)

        return d


tzmap = {"utc": "UTC", "et": "EST", "est": "EST", "pt": "PST", "pst": "PST"}

TIMEZONE = click.Choice(list(tzmap.keys()) + ["unix"], case_sensitive=False)
FTYPE = FType()
OTYPE = OType()
FLAG = Flag()
OPINION = Opinion()
TIME = Time()
REVISION = Revision()
NULL_TIME = Time(allow_null=True)
FREQ = ListOfType("frequency list", int)
INPUTS = ListOfType("input list", int)
JSON = JsonDictType()


# Click command definitions
# =========================


@db.atomic(read_write=True)
@click.group()
def cli():
    """CHIME data flagging tool."""


@cli.group("opinion_type")
def opinion_type():
    """View and modify data flagging opinion types."""
    pass


@opinion_type.command("list")
def opinion_type_list():
    """List known flagging opinion types."""
    for type_ in orm.DataFlagOpinionType.select():
        click.echo(type_.name)


@opinion_type.command("create")
@click.argument("name")
@click.option(
    "--description", help="Description of flagging opinion type.", default=None
)
@click.option(
    "--metadata", type=JSON, help="Extra metadata as as JSON dict.", default=None
)
@click.option("--force", "-f", is_flag=True, help="Create without prompting.")
def create_opinion_type(name, description, metadata, force):
    """Create a new data flag opinion type with given NAME, and optional description and metadata."""
    type_ = orm.DataFlagOpinionType()

    type_.name = name
    type_.description = description
    type_.metadata = metadata

    if force:
        type_.save()
    else:
        click.echo("Type to create:\n")
        click.echo(format_type(type_))
        if click.confirm("Create type?"):
            type_.save()
            click.echo("Success.")
        else:
            click.echo("Aborted.")


@opinion_type.command("show")
@click.argument("opinion_type", type=OTYPE, metavar="TYPE")
def show_opinion_type(opinion_type):
    """Show details of the specified opinion TYPE."""
    click.echo(format_type(opinion_type))


@cli.group("opinion")
def opinion():
    """Insert data flagging opinions."""
    pass


@opinion.command("create")
@click.argument("type_", type=OTYPE, metavar="TYPE")
@click.argument("lsd", type=int)
@click.argument(
    "decision",
    type=click.Choice(orm.DataFlagOpinion.decision.enum_list, case_sensitive=False),
)
@click.option(
    "--user",
    "-u",
    help="Wiki user adding the flag opinion. If no user is supplied, the name of the local user is used.",
    default=None,
)
@click.option(
    "--notes",
    "-n",
    help="Optional comments on the decision.",
    default=None,
    type=str,
)
@click.option("--revision", "-r", type=REVISION, required=True)
@click.option("--force", "-f", is_flag=True, help="Create without prompting.")
def create_opinion(
    type_,
    lsd,
    decision,
    user,
    revision,
    notes,
    force,
):
    """Create a new data flagging opinion with given TYPE and LSD."""
    try:
        wikiuser = db.mediawiki.MediaWikiUser.get(
            user_name=user if user else get_user()
        )
    except pw.DoesNotExist:
        raise click.BadParameter(
            "Unknown user '%s'. Supply a valid MediaWiki username with -u <user>."
            % user,
            param_hint="user",
        )

    # get client
    client, _ = orm.DataFlagClient.get_or_create(
        client_name=__name__, client_version=__version__
    )

    opinion = orm.DataFlagOpinion()

    opinion.type = type_
    opinion.lsd = lsd
    opinion.decision = decision
    opinion.user = wikiuser
    opinion.client = client
    now = arrow.utcnow().int_timestamp
    opinion.creation_time = now
    opinion.last_edit = now
    opinion.revision = revision
    opinion.notes = notes

    if force:
        opinion.save()
    else:
        click.echo("Flagging opinion to create:\n")
        click.echo(format_opinion(opinion))
        if click.confirm("Create flagging opinion?"):
            opinion.save()
            click.echo("Success.")
        else:
            click.echo("Aborted.")


@opinion.command("list")
@click.option(
    "--type",
    "type_",
    type=OTYPE,
    metavar="TYPE",
    default=None,
    help="Type of flagging opinion to list. If not set, list all opinions.",
)
def opinion_list(type_):
    """List known revisions of TYPE."""

    query = orm.DataFlagOpinion.select()

    if type_:
        query = query.where(orm.DataFlagOpinion.type == type_)

    query = query.join(orm.DataFlagOpinionType)

    rows = []
    for opinion in query:
        rows.append(
            (
                opinion.id,
                opinion.decision,
                opinion.type.name,
                opinion.lsd,
                opinion.user.user_name,
                opinion.notes,
                format_time(opinion.creation_time),
            )
        )

    table = tabulate.tabulate(
        rows,
        headers=("id", "decision", "type", "lsd", "user", "notes", "creation_time"),
    )
    click.echo(table)


@opinion.command("show")
@click.argument("opinion", type=OPINION, metavar="ID")
@click.option("--time", type=TIMEZONE, default="utc")
def opinion_show(opinion, time):
    """Show information about the flagging opinion with ID."""

    click.echo(format_opinion(opinion, time))


@opinion.command("edit")
@click.argument("opinion", type=OPINION, metavar="ID")
@click.option(
    "--decision",
    type=click.Choice(orm.DataFlagOpinion.decision.enum_list, case_sensitive=False),
)
@click.option(
    "--type",
    "type_",
    type=OTYPE,
    metavar="TYPE",
    default=None,
    help="Change the type of the flagging opinion.",
)
@click.option(
    "--user", help="Change the wiki user who created the flag opinion.", default=None
)
@click.option(
    "--lsd",
    type=int,
    default=None,
    help="Change the Local Sidereal Day.",
)
@click.option(
    "--notes",
    type=str,
    default=None,
    help="Change the comment on the decision.",
)
@click.option("--force", "-f", is_flag=True, help="Create without prompting.")
def opinion_edit(
    opinion,
    decision,
    type_,
    lsd,
    notes,
    force,
    user,
):
    """Edit the existing opinion with ID.

    You can change all required and metadata parameters.
    """
    if user:
        try:
            wikiuser = db.mediawiki.MediaWikiUser.get(
                user_name=user if user else get_user()
            )
        except pw.DoesNotExist:
            raise click.BadParameter(
                "Unknown user '%s'. Supply a valid MediaWiki username with -u <user>."
                % user,
                param_hint="user",
            )
        opinion.user = wikiuser

    if decision:
        opinion.decision = decision

    if type_:
        opinion.type = type_

    if lsd:
        opinion.lsd = lsd

    if notes:
        opinion.notes = notes

    opinion.last_edit = arrow.utcnow().int_timestamp

    if force:
        opinion.save()
    else:
        click.echo("Edited opinion:\n")
        click.echo(format_opinion(opinion))
        if click.confirm("Commit changed opinion?"):
            opinion.save()
            click.echo("Success.")
        else:
            click.echo("Aborted.")


@opinion.command("vote")
@click.option(
    "--verbose", "-v", is_flag=True, default=False, help="Verbosely print results."
)
@click.option(
    "--mode",
    "-m",
    required=True,
    type=click.Choice(VotingJudge.mode_choices, case_sensitive=False),
    help="Mode to use for translation from opinions to falgs.",
)
@click.option("--revision", "-r", type=REVISION, required=True)
def opinion_vote(mode, verbose, revision):
    """Update data flags with vote from opinions."""
    judge = VotingJudge(mode, revision)
    flags = judge.vote()
    if verbose is True:
        click.echo("Vote resulted in %i flags:" % len(flags))
        for f in flags:
            format_flag(f)


@cli.group("type")
def type_():
    """View and modify data flag types."""
    pass


@cli.group()
def flag():
    """View and modify flagged ranges of data."""
    pass


@type_.command("list")
def type_list():
    """List known flag types."""
    for type_ in orm.DataFlagType.select():
        click.echo(type_.name)


@type_.command("create")
@click.argument("name")
@click.option("--description", help="Description of flag type.", default=None)
@click.option(
    "--metadata", type=JSON, help="Extra metadata as as JSON dict.", default=None
)
@click.option("--force", "-f", is_flag=True, help="Create without prompting.")
def create_type(name, description, metadata, force):
    """Create a new data flag type with given NAME, and optional description and metadata."""
    type_ = orm.DataFlagType()

    type_.name = name
    type_.description = description
    type_.metadata = metadata

    if force:
        type_.save()
    else:
        click.echo("Type to create:\n")
        click.echo(format_type(type_))
        if click.confirm("Create type?"):
            type_.save()
            click.echo("Success.")
        else:
            click.echo("Aborted.")


@type_.command("show")
@click.argument("type_", type=FTYPE, metavar="TYPE")
def show_type(type_):
    """Show details of the specified TYPE."""
    click.echo(format_type(type_))


@flag.command("list")
@click.option(
    "--type",
    "type_",
    type=FTYPE,
    metavar="TYPE",
    default=None,
    help="Type of flag to list. If not set, list all flags.",
)
@click.option(
    "--time",
    type=TIMEZONE,
    default="utc",
    help="Timezone/format to display times in. UNIX time gives a UNIX time in seconds.",
)
@click.option(
    "--start",
    type=TIME,
    default=None,
    help="Return only flags active after this point. Accepts any string that `arrow` understands, "
    'ISO8601 is recommended, e.g. "2019-10-25T12:34:56Z".',
)
@click.option(
    "--finish",
    type=TIME,
    default=None,
    help="Return only flags active before this point. Accepts the same format as `--start`",
)
def flag_list(type_, time, start, finish):
    """List known revisions of TYPE."""

    query = orm.DataFlag.select()

    if type_:
        query = query.where(orm.DataFlag.type == type_)

    # Add the filters on start/end times
    if start:
        query = query.where(
            (orm.DataFlag.finish_time >= start.int_timestamp)
            | orm.DataFlag.finish_time.is_null()
        )
    if finish:
        query = query.where(orm.DataFlag.start_time <= finish.int_timestamp)

    query = query.join(orm.DataFlagType)

    rows = []
    for flag in query:
        rows.append(
            (
                flag.id,
                flag.type.name,
                format_time(flag.start_time),
                format_time(flag.finish_time),
            )
        )

    table = tabulate.tabulate(rows, headers=("id", "type", "start", "finish"))
    click.echo(table)


@flag.command("show")
@click.argument("flag", type=FLAG, metavar="ID")
@click.option("--time", type=TIMEZONE, default="utc")
def flag_show(flag, time):
    """Show information about the flag with ID."""

    click.echo(format_flag(flag, time))


@flag.command("create")
@click.argument("type_", type=FTYPE, metavar="TYPE")
@click.argument("start", type=TIME)
@click.argument("finish", type=NULL_TIME)
@click.option("--description", help="Description of flag.", default=None)
@click.option(
    "--user",
    help="User adding the flag. If not set explicitly this is looked up from the current username.",
    default=None,
)
@click.option(
    "--instrument",
    type=click.Choice(["chime", "pathfinder"]),
    help="Name of instrument to apply flag to.",
    default=None,
)
@click.option("--freq", type=FREQ, help="List of frequency IDs to flag.", default=None)
@click.option("--inputs", type=INPUTS, help="List of input IDs to flag.", default=None)
@click.option(
    "--metadata", type=JSON, help="Extra metadata as as JSON dict.", default=None
)
@click.option("--force", "-f", is_flag=True, help="Create without prompting.")
def create_flag(
    type_, start, finish, instrument, description, user, freq, inputs, metadata, force
):
    """Create a new data flag with given TYPE and START and FINISH times.

    Times can be supplied in any format recognized by the `arrow` library. Using
    the YYYY-MM-DDTHH:MM:SSZ format is recommended. If the flag has not ended,
    supply the string 'null' instead.

    Optionally you can set the instrument, inputs and frequencies effected as
    well as generic metadata.
    """
    flag = orm.DataFlag()

    flag.type = type_
    flag.start_time = start.int_timestamp
    flag.finish_time = finish.int_timestamp if finish != "null" else None

    if metadata is None:
        metadata = {}

    # Add any optional metadata
    if description:
        metadata["description"] = description
    if instrument:
        metadata["instrument"] = instrument
    if inputs:
        metadata["inputs"] = inputs
    if freq:
        metadata["freq"] = freq

    # Set the name of the user entering the flag
    metadata["user"] = user if user else get_user()

    flag.metadata = metadata

    if force:
        flag.save()
    else:
        click.echo("Flag to create:\n")
        click.echo(format_flag(flag))
        if click.confirm("Create flag?"):
            flag.save()
            click.echo("Success.")
        else:
            click.echo("Aborted.")


@flag.command("edit")
@click.argument("flag", type=FLAG, metavar="ID")
@click.option(
    "--type",
    "type_",
    type=FTYPE,
    metavar="TYPE",
    default=None,
    help="Change the type of the flag.",
)
@click.option(
    "--start",
    type=TIME,
    default=None,
    help="Change the flag start time in format YYYY-MM-DDTHH:MM:SSZ.",
)
@click.option(
    "--finish",
    type=TIME,
    default=None,
    help="Change the flag end time in format YYYY-MM-DDTHH:MM:SSZ. If the flag has not ended supply the string 'null'.",
)
@click.option(
    "--instrument",
    type=click.Choice(["chime", "pathfinder"]),
    help="Add/change an instrument.",
    default=None,
)
@click.option(
    "--description", help="Add/change the description of the flag.", default=None
)
@click.option(
    "--user", help="Change the record of the user that added the flag.", default=None
)
@click.option(
    "--freq",
    type=FREQ,
    help="Add/change the list of frequency IDs to flag.",
    default=None,
)
@click.option(
    "--inputs",
    type=INPUTS,
    help="Add/change the list of input IDs to flag.",
    default=None,
)
@click.option(
    "--metadata", type=JSON, help="Add/change the extra metadata.", default=None
)
@click.option("--force", "-f", is_flag=True, help="Create without prompting.")
def edit_flag(
    flag,
    type_,
    start,
    finish,
    instrument,
    description,
    user,
    freq,
    inputs,
    metadata,
    force,
):
    """Edit the existing flag with ID.

    You can change all required and metadata parameters.
    """
    if type_:
        flag.type = type_

    if start:
        flag.start_time = start.int_timestamp

    if finish:
        flag.finish_time = finish.int_timestamp if finish != "null" else None

    if metadata:
        flag.metadata.update(metadata)

    # Edit any optional metadata
    if description:
        flag.metadata["description"] = description
    if user:
        flag.metadata["user"] = user
    if instrument:
        flag.metadata["instrument"] = instrument
    if inputs:
        flag.metadata["inputs"] = inputs
    if freq:
        flag.metadata["freq"] = freq

    if force:
        flag.save()
    else:
        click.echo("Edited flag:\n")
        click.echo(format_flag(flag))
        if click.confirm("Commit changed flag?"):
            flag.save()
            click.echo("Success.")
        else:
            click.echo("Aborted.")


@cli.group("revision")
def revision():
    """Insert, view and modify data revisions."""
    pass


@revision.command("list")
def revision_list():
    """List known data revisions."""
    for rev in orm.DataRevision.select():
        click.echo(rev.name)


@revision.command("create")
@click.argument("name")
@click.option("--description", help="Description of data revision.", default=None)
@click.option("--force", "-f", is_flag=True, help="Create without prompting.")
def create_revision(name, description, force):
    """Create a new data revision with given NAME, and optional description."""
    revision = orm.DataRevision()

    revision.name = name
    revision.description = description

    if force:
        revision.save()
    else:
        click.echo("Revision to create:\n")
        click.echo(format_revision(revision))
        if click.confirm("Create revision?"):
            revision.save()
            click.echo("Success.")
        else:
            click.echo("Aborted.")


@revision.command("show")
@click.argument("revision", type=REVISION, metavar="REVISION")
def show_revision(revision):
    """Show details of the specified REVISION."""
    click.echo(format_revision(revision))


def format_time(time, timefmt="utc"):
    if time is None:
        return "null"
    if timefmt == "unix":
        return time
    return arrow.get(time).to(tzmap[timefmt]).format()


def format_metadata(metadata):
    s = yaml.dump(metadata)
    if len(s) and s[-1] == "\n":
        s = s[:-1]
    return re.sub("^", "    ", s, flags=re.MULTILINE)


def format_flag(flag, timefmt="utc"):
    template = """<b>id</b>: {id}
<b>type</b>: {type}
<b>start</b>: {start}
<b>finish</b>: {finish}
<b>metadata</b>: {metadata}"""

    metadata = "" if flag.metadata is None else "\n" + format_metadata(flag.metadata)

    tdict = {
        "id": flag.id,
        "start": format_time(flag.start_time, timefmt),
        "finish": format_time(flag.finish_time, timefmt),
        "metadata": metadata,
        "type": flag.type.name,
    }

    return ansimarkup.parse(template.format(**tdict))


def format_type(type_):
    template = """<b>type</b>: {type}
<b>description</b>: {description}
<b>metadata</b>: {metadata}"""

    metadata = "" if type_.metadata is None else "\n" + format_metadata(type_.metadata)

    tdict = {
        "type": type_.name,
        "description": type_.description if type_.description else "",
        "metadata": metadata,
    }

    return ansimarkup.parse(template.format(**tdict))


def format_opinion(opinion, timefmt="utc"):
    template = """<b>id</b>: {id}
<b>decision</b>: {decision}
<b>type</b>: {type}
<b>lsd</b>: {lsd}
<b>user</b>: {user}
<b>client</b>: {client_name} ({client_version})
<b>notes</b>: {notes}
<b>creation_time</b>: {creation_time}
<b>last_edit</b>: {last_edit}
"""

    tdict = {
        "id": opinion.id,
        "lsd": opinion.lsd,
        "type": opinion.type.name,
        "user": opinion.user.user_name,
        "client_name": opinion.client.client_name,
        "client_version": opinion.client.client_version,
        "notes": opinion.notes,
        "decision": opinion.decision,
        "creation_time": format_time(opinion.creation_time, timefmt),
        "last_edit": format_time(opinion.last_edit, timefmt),
    }

    return ansimarkup.parse(template.format(**tdict))


def format_revision(revision):
    template = """<b>name</b>: {name}
<b>descriptions</b>: {description}"""

    tdict = {
        "name": revision.name,
        "description": revision.description,
    }

    return ansimarkup.parse(template.format(**tdict))


def get_user():
    return pwd.getpwuid(os.getuid()).pw_gecos.split(",")[0]


if __name__ == "__main__":
    cli()
