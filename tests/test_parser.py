"""Unit tests for xclif.parser."""

import pytest

from xclif.command import Command
from xclif.definition import Option
from xclif.parser import _parse_token_stream, parse_and_execute_impl


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _opt(name: str, typ: type, default=None) -> Option:
    return Option(name, typ, "desc", default=default)


def _bool_opts(*names: str) -> dict[str, Option]:
    return {n: _opt(n, bool) for n in names}


def _str_opts(*names: str) -> dict[str, Option]:
    return {n: _opt(n, str) for n in names}


# ---------------------------------------------------------------------------
# _parse_token_stream — boolean flags
# ---------------------------------------------------------------------------


def test_bool_flag_collected():
    _, opts, idx = _parse_token_stream(_bool_opts("verbose"), {}, ["--verbose"])
    assert opts["verbose"] == [True]
    assert idx is None


def test_bool_flag_repeated():
    _, opts, idx = _parse_token_stream(_bool_opts("verbose"), {}, ["--verbose", "--verbose"])
    assert opts["verbose"] == [True, True]


def test_bool_flag_empty():
    pos, opts, idx = _parse_token_stream(_bool_opts("verbose"), {}, [])
    assert pos == []
    assert opts == {}
    assert idx is None


# ---------------------------------------------------------------------------
# _parse_token_stream — value options
# ---------------------------------------------------------------------------


def test_str_option_consumes_next_token():
    _, opts, _ = _parse_token_stream(_str_opts("name"), {}, ["--name", "Alice"])
    assert opts["name"] == ["Alice"]


def test_int_option_converts():
    opts_def = {"count": _opt("count", int)}
    _, opts, _ = _parse_token_stream(opts_def, {}, ["--count", "42"])
    assert opts["count"] == [42]


def test_hyphenated_option_maps_to_snake():
    opts_def = {"dry_run": _opt("dry_run", bool)}
    _, opts, _ = _parse_token_stream(opts_def, {}, ["--dry-run"])
    assert opts["dry_run"] == [True]


def test_repeated_value_option():
    _, opts, _ = _parse_token_stream(_str_opts("tag"), {}, ["--tag", "a", "--tag", "b"])
    assert opts["tag"] == ["a", "b"]


# ---------------------------------------------------------------------------
# _parse_token_stream — interspersed options
# ---------------------------------------------------------------------------


def test_option_before_positional():
    _, opts, _ = _parse_token_stream(_bool_opts("verbose"), {}, ["--verbose", "Alice"])
    assert opts["verbose"] == [True]


def test_positional_before_option():
    pos, opts, _ = _parse_token_stream(_bool_opts("verbose"), {}, ["Alice", "--verbose"])
    assert pos == ["Alice"]
    assert opts["verbose"] == [True]


def test_interleaved_positionals_and_options():
    all_opts = {**_str_opts("template"), **_bool_opts("verbose")}
    pos, opts, _ = _parse_token_stream(
        all_opts, {}, ["Alice", "--template", "Hi {}!", "--verbose", "Bob"]
    )
    assert pos == ["Alice", "Bob"]
    assert opts["template"] == ["Hi {}!"]
    assert opts["verbose"] == [True]


# ---------------------------------------------------------------------------
# _parse_token_stream — subcommand detection stops scan
# ---------------------------------------------------------------------------


def test_subcommand_stops_scan():
    subcmds = {"greet": Command("greet", lambda: 0)}
    pos, opts, idx = _parse_token_stream({}, subcmds, ["greet", "Alice"])
    assert idx == 0
    assert pos == []


def test_option_before_subcommand_is_collected():
    all_opts = _bool_opts("verbose")
    subcmds = {"greet": Command("greet", lambda: 0)}
    _, opts, idx = _parse_token_stream(all_opts, subcmds, ["--verbose", "greet"])
    assert opts["verbose"] == [True]
    assert idx == 1


def test_value_option_consuming_subcommand_name_as_value():
    """The greedy rule: --format json eats 'json' even if 'json' is a subcommand."""
    all_opts = _str_opts("format")
    subcmds = {"json": Command("json", lambda: 0)}
    pos, opts, idx = _parse_token_stream(all_opts, subcmds, ["--format", "json"])
    # json was consumed as the value of --format, not as a subcommand
    assert opts["format"] == ["json"]
    assert idx is None


def test_second_token_invokes_subcommand_after_greedy_consumption():
    all_opts = _str_opts("format")
    subcmds = {"json": Command("json", lambda: 0)}
    pos, opts, idx = _parse_token_stream(all_opts, subcmds, ["--format", "json", "json"])
    assert opts["format"] == ["json"]
    assert idx == 2  # second 'json' is the subcommand


# ---------------------------------------------------------------------------
# _parse_token_stream — error cases
# ---------------------------------------------------------------------------


def test_unknown_option_raises():
    with pytest.raises(RuntimeError, match="Unknown option"):
        _parse_token_stream({}, {}, ["--nope"])


def test_value_option_missing_value_raises():
    with pytest.raises(RuntimeError, match="requires a value"):
        _parse_token_stream(_str_opts("name"), {}, ["--name"])


def test_short_option_raises_not_implemented():
    with pytest.raises(NotImplementedError):
        _parse_token_stream({}, {}, ["-v"])


def test_double_dash_raises_not_implemented():
    with pytest.raises(NotImplementedError):
        _parse_token_stream({}, {}, ["--"])


# ---------------------------------------------------------------------------
# parse_and_execute_impl — leaf commands
# ---------------------------------------------------------------------------


def test_leaf_no_args_executes(capsys):
    def run() -> None:
        print("ran")

    cmd = Command("test", run)
    result = parse_and_execute_impl([], cmd)
    assert result == 0
    assert "ran" in capsys.readouterr().out


def test_leaf_positional_arg_passed(capsys):
    received = []

    def run(name: str) -> None:
        received.append(name)

    from xclif.definition import Argument
    cmd = Command("test", run, arguments=[Argument("name", str, "desc")])
    parse_and_execute_impl(["Alice"], cmd)
    assert received == ["Alice"]


def test_leaf_option_passed():
    received = {}

    def run(greeting: str = "hi") -> None:
        received["greeting"] = greeting

    cmd = Command("test", run, options={"greeting": Option("greeting", str, "desc", "hi")})
    parse_and_execute_impl(["--greeting", "hello"], cmd)
    assert received["greeting"] == "hello"


def test_leaf_option_default_used():
    received = {}

    def run(greeting: str = "hi") -> None:
        received["greeting"] = greeting

    cmd = Command("test", run, options={"greeting": Option("greeting", str, "desc", "hi")})
    parse_and_execute_impl([], cmd)
    assert received["greeting"] == "hi"


def test_leaf_missing_required_arg_raises():
    from xclif.definition import Argument
    cmd = Command("test", lambda name: None, arguments=[Argument("name", str, "desc")])
    with pytest.raises(RuntimeError, match="Missing required argument"):
        parse_and_execute_impl([], cmd)


def test_leaf_interspersed_option_and_positional(capsys):
    received = {}

    def run(name: str, greeting: str = "hi") -> None:
        received["name"] = name
        received["greeting"] = greeting

    from xclif.definition import Argument
    cmd = Command(
        "test", run,
        arguments=[Argument("name", str, "desc")],
        options={"greeting": Option("greeting", str, "desc", "hi")},
    )
    parse_and_execute_impl(["--greeting", "hey", "Alice"], cmd)
    assert received == {"name": "Alice", "greeting": "hey"}


# ---------------------------------------------------------------------------
# parse_and_execute_impl — implicit options
# ---------------------------------------------------------------------------


def test_help_flag_returns_zero_and_prints(capsys):
    cmd = Command("test", lambda: 0)
    result = parse_and_execute_impl(["--help"], cmd)
    assert result == 0
    # rich prints something
    assert capsys.readouterr().out != ""


def test_implicit_options_not_forwarded_to_run():
    """--verbose must not appear in run()'s kwargs."""
    received_kwargs = {}

    def run(**kwargs) -> None:
        received_kwargs.update(kwargs)

    # A command with no declared options
    cmd = Command("test", run)
    parse_and_execute_impl(["--verbose"], cmd)
    assert "verbose" not in received_kwargs
    assert "help" not in received_kwargs


# ---------------------------------------------------------------------------
# parse_and_execute_impl — cascading context
# ---------------------------------------------------------------------------


def test_cascading_verbose_passed_to_context():
    """--verbose at parent level should update the context for children."""
    context_seen = {}

    def child_run() -> None:
        pass

    child = Command("child", child_run)

    def parent_run() -> None:
        pass

    parent = Command("parent", parent_run, subcommands={"child": child})

    # We test the context by inspecting parse_and_execute_impl's behaviour:
    # if --verbose is parsed before 'child', the child should be called without error
    result = parse_and_execute_impl(["--verbose", "child"], parent)
    assert result == 0


def test_verbose_not_in_child_run_kwargs():
    """Even when --verbose cascades, it must not appear in child's run() kwargs."""
    received = {}

    def child_run(**kwargs) -> None:
        received.update(kwargs)

    child = Command("child", child_run)
    parent = Command("parent", lambda: 0, subcommands={"child": child})

    parse_and_execute_impl(["--verbose", "child"], parent)
    assert "verbose" not in received


# ---------------------------------------------------------------------------
# parse_and_execute_impl — namespace default action
# ---------------------------------------------------------------------------


def test_namespace_no_args_prints_help(capsys):
    child = Command("sub", lambda: 0)
    parent = Command("parent", lambda: 0, subcommands={"sub": child})
    result = parse_and_execute_impl([], parent)
    assert result == 0
    assert capsys.readouterr().out != ""


def test_unknown_subcommand_raises():
    child = Command("sub", lambda: 0)
    parent = Command("parent", lambda: 0, subcommands={"sub": child})
    with pytest.raises(RuntimeError, match="Unknown subcommand"):
        parse_and_execute_impl(["doesnotexist"], parent)
