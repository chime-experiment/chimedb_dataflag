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

from . import orm
from chimedb.core.orm import connect_database


# Custom parameter types for click arguments
# ==========================================


class FType(click.ParamType):
    """Flag type parameter for click."""

    name = "flag type"

    def convert(self, value, param, ctx):

        # Connect if needed
        connect_database(read_write=False)

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

        # Connect if needed
        connect_database(read_write=False)

        try:
            f = orm.DataFlag.get(id=value)
        except pw.NotFound:
            self.fail(
                'flag id "%i" unknown. See `cdf flag list` ' "for valid ids." % value
            )

        return f


class Time(click.ParamType):
    """Time parameter for click. Supports any format that arrow can parse."""

    name = "time"

    def convert(self, value, param, ctx):

        try:
            return arrow.get(value)
        except arrow.parser.ParserError as e:
            self.fail('Could not parse time "%s": %s' % (value, e.message))


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
FLAG = Flag()
TIME = Time()
FREQ = ListOfType("frequency list", int)
INPUTS = ListOfType("input list", int)
JSON = JsonDictType()


# Click command definitions
# =========================


@click.group()
def cli():
    """CHIME data flagging tool."""


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
    connect_database(read_write=False)

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
    """Create a new data flag type with given NAME, and optional description and metadata.
    """
    connect_database(read_write=True)

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
    help='Return only flags active after this point. Accepts any string that `arrow` understands, ISO8601 is recommended, e.g. "2019-10-25T12:34:56Z".',
)
@click.option(
    "--finish",
    type=TIME,
    default=None,
    help="Return only flags active before this point. Accepts the same format as `--start`",
)
def flag_list(type_, time, start, finish):
    """List known revisions of TYPE."""

    connect_database(read_write=False)

    query = orm.DataFlag.select()

    if type_:
        query = query.where(orm.DataFlag.type == type_)

    # Add the filters on start/end times
    if start:
        query = query.where(orm.DataFlag.finish_time >= start.timestamp)
    if finish:
        query = query.where(orm.DataFlag.start_time <= finish.timestamp)

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

    connect_database(read_write=False)

    click.echo(format_flag(flag, time))


@flag.command("create")
@click.argument("type_", type=FTYPE, metavar="TYPE")
@click.argument("start", type=TIME)
@click.argument("finish", type=TIME)
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
@click.option("--force", is_flag=True, help="Create without prompting.")
def create_flag(
    type_, start, finish, instrument, description, user, freq, inputs, metadata, force
):
    """Create a new data flag with given TYPE and START and FINISH times.

    Optionally you can set the instrument, inputs and frequencies effected as
    well as generic metadata.
    """
    connect_database(read_write=True)

    flag = orm.DataFlag()

    flag.type = type_
    flag.start_time = start.timestamp
    flag.finish_time = finish.timestamp

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
@click.option("--start", type=TIME, default=None, help="Change the flag start time.")
@click.option("--finish", type=TIME, default=None, help="Change the flag end time.")
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
@click.option(
    "--force", type=bool, help="Change the flag without prompting.", default=None
)
def edit_flag(flag, type_, start, finish, instrument, freq, inputs, metadata, force):
    """Edit the existing flag with ID.

    You can change all required and metadata parameters.
    """
    connect_database(read_write=True)

    if type_:
        flag.type = type_

    if start:
        flag.start_time = start.timestamp

    if finish:
        flag.finish_time = finish.timestamp

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


def format_time(time, timefmt="utc"):
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


def get_user():
    return pwd.getpwuid(os.getuid()).pw_gecos.split(",")[0]


if __name__ == "__main__":
    cli()
