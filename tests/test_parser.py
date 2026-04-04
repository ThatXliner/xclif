"""Unit tests for xclif.parser."""

import pytest

from xclif import WithConfig
from xclif.command import Command
from xclif.definition import Argument, Option
from xclif.errors import UsageError
from xclif.parser import _parse_token_stream, parse_and_execute_impl


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _opt(name: str, typ: type, default=None, aliases=None) -> Option:
    return Option(name, typ, "desc", default=default, aliases=aliases or [])


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
# _parse_token_stream — value options (space form)
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
# _parse_token_stream — equals form (--name=value)
# ---------------------------------------------------------------------------


def test_equals_form_str():
    _, opts, _ = _parse_token_stream(_str_opts("name"), {}, ["--name=Alice"])
    assert opts["name"] == ["Alice"]


def test_equals_form_int():
    opts_def = {"count": _opt("count", int)}
    _, opts, _ = _parse_token_stream(opts_def, {}, ["--count=42"])
    assert opts["count"] == [42]


def test_equals_form_value_with_equals():
    """--url=https://example.com/path?a=1 should parse correctly."""
    _, opts, _ = _parse_token_stream(_str_opts("url"), {}, ["--url=https://a.com?b=1"])
    assert opts["url"] == ["https://a.com?b=1"]


def test_equals_form_bool_raises():
    with pytest.raises(UsageError, match="does not take a value"):
        _parse_token_stream(_bool_opts("verbose"), {}, ["--verbose=true"])


def test_equals_form_unknown_raises():
    with pytest.raises(UsageError, match="Unknown option"):
        _parse_token_stream({}, {}, ["--nope=val"])


# ---------------------------------------------------------------------------
# _parse_token_stream — short options
# ---------------------------------------------------------------------------


def test_short_bool_flag():
    opts = {"verbose": _opt("verbose", bool, aliases=["-v"])}
    _, parsed, _ = _parse_token_stream(opts, {}, ["-v"])
    assert parsed["verbose"] == [True]


def test_short_value_option():
    opts = {"name": _opt("name", str, aliases=["-n"])}
    _, parsed, _ = _parse_token_stream(opts, {}, ["-n", "Alice"])
    assert parsed["name"] == ["Alice"]


def test_short_repeated():
    opts = {"verbose": _opt("verbose", bool, aliases=["-v"])}
    _, parsed, _ = _parse_token_stream(opts, {}, ["-v", "-v", "-v"])
    assert parsed["verbose"] == [True, True, True]


def test_short_mixed_with_long():
    opts = {"verbose": _opt("verbose", bool, aliases=["-v"])}
    _, parsed, _ = _parse_token_stream(opts, {}, ["-v", "--verbose"])
    assert parsed["verbose"] == [True, True]


def test_short_unknown_raises():
    with pytest.raises(UsageError, match="Unknown option"):
        _parse_token_stream({}, {}, ["-x"])


def test_short_value_missing_raises():
    opts = {"name": _opt("name", str, aliases=["-n"])}
    with pytest.raises(UsageError, match="requires a value"):
        _parse_token_stream(opts, {}, ["-n"])


# ---------------------------------------------------------------------------
# _parse_token_stream — -- separator
# ---------------------------------------------------------------------------


def test_double_dash_dumps_rest_as_positionals():
    pos, opts, _ = _parse_token_stream(_bool_opts("verbose"), {}, ["--", "--verbose", "foo"])
    assert pos == ["--verbose", "foo"]
    assert opts == {}


def test_double_dash_after_option():
    opts_def = _bool_opts("verbose")
    pos, opts, _ = _parse_token_stream(opts_def, {}, ["--verbose", "--", "--not-a-flag"])
    assert opts["verbose"] == [True]
    assert pos == ["--not-a-flag"]


def test_double_dash_empty_rest():
    pos, _, _ = _parse_token_stream({}, {}, ["--"])
    assert pos == []


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
    assert opts["format"] == ["json"]
    assert idx is None


def test_second_token_invokes_subcommand_after_greedy_consumption():
    all_opts = _str_opts("format")
    subcmds = {"json": Command("json", lambda: 0)}
    pos, opts, idx = _parse_token_stream(all_opts, subcmds, ["--format", "json", "json"])
    assert opts["format"] == ["json"]
    assert idx == 2


# ---------------------------------------------------------------------------
# _parse_token_stream — error cases
# ---------------------------------------------------------------------------


def test_unknown_long_option_raises():
    with pytest.raises(UsageError, match="Unknown option"):
        _parse_token_stream({}, {}, ["--nope"])


def test_value_option_missing_value_raises():
    with pytest.raises(UsageError, match="requires a value"):
        _parse_token_stream(_str_opts("name"), {}, ["--name"])


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


def test_leaf_positional_arg_passed():
    received = []

    def run(name: str) -> None:
        received.append(name)

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
    cmd = Command("test", lambda name: None, arguments=[Argument("name", str, "desc")])
    with pytest.raises(UsageError, match="Missing required argument"):
        parse_and_execute_impl([], cmd)


def test_leaf_interspersed_option_and_positional():
    received = {}

    def run(name: str, greeting: str = "hi") -> None:
        received["name"] = name
        received["greeting"] = greeting

    cmd = Command(
        "test", run,
        arguments=[Argument("name", str, "desc")],
        options={"greeting": Option("greeting", str, "desc", "hi")},
    )
    parse_and_execute_impl(["--greeting", "hey", "Alice"], cmd)
    assert received == {"name": "Alice", "greeting": "hey"}


def test_leaf_equals_form_option():
    received = {}

    def run(greeting: str = "hi") -> None:
        received["greeting"] = greeting

    cmd = Command("test", run, options={"greeting": Option("greeting", str, "desc", "hi")})
    parse_and_execute_impl(["--greeting=hey"], cmd)
    assert received["greeting"] == "hey"


# ---------------------------------------------------------------------------
# parse_and_execute_impl — variadic positional args
# ---------------------------------------------------------------------------


def test_variadic_consumes_all_positionals():
    received = []

    def run(*files: str) -> None:
        received.extend(files)

    cmd = Command("add", run, arguments=[Argument("files", str, "Files to add", variadic=True)])
    parse_and_execute_impl(["a.py", "b.py", "c.py"], cmd)
    assert received == ["a.py", "b.py", "c.py"]


def test_variadic_zero_args():
    received = []

    def run(*files: str) -> None:
        received.extend(files)

    cmd = Command("add", run, arguments=[Argument("files", str, "Files to add", variadic=True)])
    parse_and_execute_impl([], cmd)
    assert received == []


def test_variadic_with_fixed_args():
    received = {}

    def run(dest: str, *files: str) -> None:
        received["dest"] = dest
        received["files"] = list(files)

    cmd = Command(
        "cp", run,
        arguments=[
            Argument("dest", str, "Destination"),
            Argument("files", str, "Files to copy", variadic=True),
        ],
    )
    parse_and_execute_impl(["target/", "a.py", "b.py"], cmd)
    assert received == {"dest": "target/", "files": ["a.py", "b.py"]}


def test_variadic_with_options():
    received = {}

    def run(*files: str, recursive: str = "false") -> None:
        received["files"] = list(files)
        received["recursive"] = recursive

    cmd = Command(
        "rm", run,
        arguments=[Argument("files", str, "Files", variadic=True)],
        options={"recursive": Option("recursive", str, "Recursive", "false")},
    )
    parse_and_execute_impl(["--recursive", "true", "a.py", "b.py"], cmd)
    assert received == {"files": ["a.py", "b.py"], "recursive": "true"}


def test_variadic_with_double_dash():
    received = []

    def run(*files: str) -> None:
        received.extend(files)

    cmd = Command("add", run, arguments=[Argument("files", str, "Files", variadic=True)])
    parse_and_execute_impl(["a.py", "--", "--not-a-flag"], cmd)
    assert received == ["a.py", "--not-a-flag"]


# ---------------------------------------------------------------------------
# parse_and_execute_impl — implicit options
# ---------------------------------------------------------------------------


def test_help_flag_returns_zero_and_prints(capsys):
    cmd = Command("test", lambda: 0)
    result = parse_and_execute_impl(["--help"], cmd)
    assert result == 0
    assert capsys.readouterr().out != ""


def test_help_short_flag_returns_zero(capsys):
    cmd = Command("test", lambda: 0)
    result = parse_and_execute_impl(["-h"], cmd)
    assert result == 0
    assert capsys.readouterr().out != ""


def test_implicit_options_not_forwarded_to_run():
    received_kwargs = {}

    def run(**kwargs) -> None:
        received_kwargs.update(kwargs)

    cmd = Command("test", run)
    parse_and_execute_impl(["--verbose"], cmd)
    assert "verbose" not in received_kwargs
    assert "help" not in received_kwargs


# ---------------------------------------------------------------------------
# parse_and_execute_impl — --version
# ---------------------------------------------------------------------------


def test_version_flag_prints_and_returns_zero(capsys):
    cmd = Command("myapp", lambda: 0, version="1.2.3")
    # Inject --version into implicit options (normally done by Cli)
    cmd.implicit_options["version"] = Option("version", bool, "Show version")
    result = parse_and_execute_impl(["--version"], cmd)
    assert result == 0
    out = capsys.readouterr().out
    assert "myapp" in out
    assert "1.2.3" in out


def test_version_flag_unknown_when_not_root(capsys):
    cmd = Command("myapp", lambda: 0)
    # No version injected → --version should be unknown
    with pytest.raises(UsageError, match="Unknown option"):
        parse_and_execute_impl(["--version"], cmd)


# ---------------------------------------------------------------------------
# parse_and_execute_impl — cascading context
# ---------------------------------------------------------------------------


def test_cascading_verbose_passed_to_context():
    child = Command("child", lambda: None)
    parent = Command("parent", lambda: None, subcommands={"child": child})
    result = parse_and_execute_impl(["--verbose", "child"], parent)
    assert result == 0


def test_verbose_not_in_child_run_kwargs():
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
    with pytest.raises(UsageError, match="Unknown subcommand"):
        parse_and_execute_impl(["doesnotexist"], parent)


# ---------------------------------------------------------------------------
# UsageError — hint / suggestion
# ---------------------------------------------------------------------------


def test_unknown_option_has_suggestion_hint():
    opts = _str_opts("name")
    with pytest.raises(UsageError) as exc_info:
        _parse_token_stream(opts, {}, ["--nme"])
    assert exc_info.value.hint is not None
    assert "--name" in exc_info.value.hint


def test_unknown_option_no_hint_when_no_match():
    opts = _str_opts("name")
    with pytest.raises(UsageError) as exc_info:
        _parse_token_stream(opts, {}, ["--zzzzz"])
    assert exc_info.value.hint is None


def test_unknown_subcommand_has_suggestion_hint():
    child = Command("greet", lambda: 0)
    parent = Command("parent", lambda: 0, subcommands={"greet": child})
    with pytest.raises(UsageError) as exc_info:
        parse_and_execute_impl(["gret"], parent)
    assert exc_info.value.hint is not None
    assert "greet" in exc_info.value.hint


# ---------------------------------------------------------------------------
# parse_and_execute_impl — list options
# ---------------------------------------------------------------------------


def test_list_option_single_value():
    received = {}

    def run(tags: list[str] = []) -> None:
        received["tags"] = tags

    cmd = Command(
        "test", run,
        options={"tags": Option("tags", str, "desc", [], is_list=True)},
    )
    parse_and_execute_impl(["--tags", "a"], cmd)
    assert received["tags"] == ["a"]


def test_list_option_multiple_values():
    received = {}

    def run(tags: list[str] = []) -> None:
        received["tags"] = tags

    cmd = Command(
        "test", run,
        options={"tags": Option("tags", str, "desc", [], is_list=True)},
    )
    parse_and_execute_impl(["--tags", "a", "--tags", "b", "--tags", "c"], cmd)
    assert received["tags"] == ["a", "b", "c"]


def test_list_option_default_empty():
    received = {}

    def run(tags: list[str] = []) -> None:
        received["tags"] = tags

    cmd = Command(
        "test", run,
        options={"tags": Option("tags", str, "desc", [], is_list=True)},
    )
    parse_and_execute_impl([], cmd)
    assert received["tags"] == []


# ---------------------------------------------------------------------------
# Command.execute — UsageError caught and formatted
# ---------------------------------------------------------------------------


def test_execute_catches_usage_error(capsys):
    cmd = Command("test", lambda name: None, arguments=[Argument("name", str, "desc")])
    result = cmd.execute([])
    assert result == 2
    err = capsys.readouterr().err
    assert "Error" in err
    assert "Missing required argument" in err


# ---------------------------------------------------------------------------
# parse_and_execute_impl — WithConfig resolution
# ---------------------------------------------------------------------------


def test_option_resolved_from_env(monkeypatch):
    """When CLI doesn't provide a value, env var is used."""
    monkeypatch.setenv("MYAPP_GREETING", "howdy")

    received = {}

    def run(greeting: str = "hi") -> None:
        received["greeting"] = greeting

    cmd = Command(
        "test", run,
        options={"greeting": Option("greeting", str, "desc", "hi", config=WithConfig())},
    )
    context = {"env_prefix": "MYAPP", "config_data": {}}
    parse_and_execute_impl([], cmd, context)
    assert received["greeting"] == "howdy"


def test_option_cli_overrides_env(monkeypatch):
    """CLI flag takes priority over env var."""
    monkeypatch.setenv("MYAPP_GREETING", "from_env")

    received = {}

    def run(greeting: str = "hi") -> None:
        received["greeting"] = greeting

    cmd = Command(
        "test", run,
        options={"greeting": Option("greeting", str, "desc", "hi", config=WithConfig())},
    )
    context = {"env_prefix": "MYAPP", "config_data": {}}
    parse_and_execute_impl(["--greeting", "from_cli"], cmd, context)
    assert received["greeting"] == "from_cli"


def test_option_resolved_from_config():
    """When CLI and env are absent, config file value is used."""
    received = {}

    def run(greeting: str = "hi") -> None:
        received["greeting"] = greeting

    cmd = Command(
        "test", run,
        options={"greeting": Option("greeting", str, "desc", "hi", config=WithConfig())},
    )
    context = {"env_prefix": "MYAPP", "config_data": {"greeting": "from_config"}}
    parse_and_execute_impl([], cmd, context)
    assert received["greeting"] == "from_config"


def test_option_env_overrides_config(monkeypatch):
    """Env var takes priority over config file."""
    monkeypatch.setenv("MYAPP_GREETING", "from_env")

    received = {}

    def run(greeting: str = "hi") -> None:
        received["greeting"] = greeting

    cmd = Command(
        "test", run,
        options={"greeting": Option("greeting", str, "desc", "hi", config=WithConfig())},
    )
    context = {"env_prefix": "MYAPP", "config_data": {"greeting": "from_config"}}
    parse_and_execute_impl([], cmd, context)
    assert received["greeting"] == "from_env"


def test_option_falls_back_to_default():
    """When no CLI, env, or config, default is used."""
    received = {}

    def run(greeting: str = "hi") -> None:
        received["greeting"] = greeting

    cmd = Command(
        "test", run,
        options={"greeting": Option("greeting", str, "desc", "hi", config=WithConfig())},
    )
    context = {"env_prefix": "MYAPP", "config_data": {}}
    parse_and_execute_impl([], cmd, context)
    assert received["greeting"] == "hi"


def test_argument_resolved_from_env(monkeypatch):
    """WithConfig argument resolved from env when not on CLI."""
    monkeypatch.setenv("MYAPP_NAME", "EnvAlice")

    received = []

    def run(name: str) -> None:
        received.append(name)

    cmd = Command(
        "test", run,
        arguments=[Argument("name", str, "desc", config=WithConfig())],
    )
    context = {"env_prefix": "MYAPP", "config_data": {}}
    parse_and_execute_impl([], cmd, context)
    assert received == ["EnvAlice"]


def test_argument_resolved_from_config():
    """WithConfig argument resolved from config when not on CLI or env."""
    received = []

    def run(name: str) -> None:
        received.append(name)

    cmd = Command(
        "test", run,
        arguments=[Argument("name", str, "desc", config=WithConfig())],
    )
    context = {"env_prefix": "MYAPP", "config_data": {"name": "ConfigAlice"}}
    parse_and_execute_impl([], cmd, context)
    assert received == ["ConfigAlice"]


def test_argument_missing_without_config_raises():
    """Required argument without WithConfig still raises."""
    cmd = Command("test", lambda name: None, arguments=[Argument("name", str, "desc")])
    context = {"env_prefix": "MYAPP", "config_data": {"name": "ConfigAlice"}}
    with pytest.raises(UsageError, match="Missing required argument"):
        parse_and_execute_impl([], cmd, context)


def test_option_custom_env_name(monkeypatch):
    """WithConfig(env='CUSTOM') uses that exact env var name."""
    monkeypatch.setenv("CUSTOM", "custom_val")

    received = {}

    def run(greeting: str = "hi") -> None:
        received["greeting"] = greeting

    cmd = Command(
        "test", run,
        options={"greeting": Option("greeting", str, "desc", "hi", config=WithConfig(env="CUSTOM"))},
    )
    context = {"env_prefix": "MYAPP", "config_data": {}}
    parse_and_execute_impl([], cmd, context)
    assert received["greeting"] == "custom_val"


def test_option_custom_config_key():
    """WithConfig(key='greet.msg') resolves a dotted path in config."""
    received = {}

    def run(greeting: str = "hi") -> None:
        received["greeting"] = greeting

    cmd = Command(
        "test", run,
        options={"greeting": Option("greeting", str, "desc", "hi", config=WithConfig(key="greet.msg"))},
    )
    context = {"env_prefix": "MYAPP", "config_data": {"greet": {"msg": "nested_val"}}}
    parse_and_execute_impl([], cmd, context)
    assert received["greeting"] == "nested_val"


def test_option_int_from_env(monkeypatch):
    """Env var value is converted using the option's converter."""
    monkeypatch.setenv("MYAPP_COUNT", "42")

    received = {}

    def run(count: int = 0) -> None:
        received["count"] = count

    cmd = Command(
        "test", run,
        options={"count": Option("count", int, "desc", 0, config=WithConfig())},
    )
    context = {"env_prefix": "MYAPP", "config_data": {}}
    parse_and_execute_impl([], cmd, context)
    assert received["count"] == 42


def test_no_config_context_skips_resolution():
    """When no config context is passed, WithConfig params use defaults normally."""
    received = {}

    def run(greeting: str = "hi") -> None:
        received["greeting"] = greeting

    cmd = Command(
        "test", run,
        options={"greeting": Option("greeting", str, "desc", "hi", config=WithConfig())},
    )
    parse_and_execute_impl([], cmd)
    assert received["greeting"] == "hi"
