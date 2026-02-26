"""Unit tests for xclif.command and xclif.definition."""

import pytest

from xclif.command import Command, command, extract_parameters
from xclif.constants import NO_DESC
from xclif.definition import Argument, Option


# ---------------------------------------------------------------------------
# extract_parameters
# ---------------------------------------------------------------------------


def test_no_params():
    def f() -> None: ...
    args, opts = extract_parameters(f)
    assert args == []
    assert opts == {}


def test_positional_argument():
    def f(name: str) -> None: ...
    args, opts = extract_parameters(f)
    assert len(args) == 1
    assert args[0].name == "name"
    assert args[0].converter is str


def test_option_with_default():
    def f(greeting: str = "hello") -> None: ...
    args, opts = extract_parameters(f)
    assert args == []
    assert "greeting" in opts
    assert opts["greeting"].default == "hello"
    assert opts["greeting"].converter is str


def test_mixed_args_and_options():
    def f(name: str, greeting: str = "hi") -> None: ...
    args, opts = extract_parameters(f)
    assert len(args) == 1
    assert args[0].name == "name"
    assert "greeting" in opts


def test_missing_annotation_raises():
    def f(name) -> None: ...
    with pytest.raises(ValueError, match="no type hint"):
        extract_parameters(f)


def test_unsupported_type_raises():
    def f(name: list) -> None: ...
    with pytest.raises(TypeError, match="Unsupported type"):
        extract_parameters(f)


def test_implicit_option_name_raises():
    def f(help: str) -> None: ...
    with pytest.raises(ValueError, match="implicit option"):
        extract_parameters(f)


def test_keyword_only_param_raises():
    def f(*, name: str) -> None: ...
    with pytest.raises(TypeError, match="unsupported"):
        extract_parameters(f)


def test_positional_only_param_raises():
    # positional-only params require / in signature
    exec_globals: dict = {}
    exec("def f(name: str, /, other: str) -> None: ...", exec_globals)
    f = exec_globals["f"]
    with pytest.raises(TypeError, match="unsupported"):
        extract_parameters(f)


# ---------------------------------------------------------------------------
# @command decorator — naming
# ---------------------------------------------------------------------------


def test_command_explicit_name():
    @command("mycmd")
    def _(name: str) -> None: ...

    assert _.name == "mycmd"


def test_command_underscore_uses_module_name():
    @command()
    def _() -> None: ...

    # When run from tests, __module__ ends in the test module name
    # The important thing is it doesn't use "_" literally
    assert _.name != "_"


def test_command_function_name_used():
    @command()
    def greet(name: str) -> None: ...

    assert greet.name == "greet"


# ---------------------------------------------------------------------------
# Command dataclass
# ---------------------------------------------------------------------------


def test_command_has_implicit_options():
    cmd = Command("test", lambda: 0)
    assert "help" in cmd.implicit_options
    assert "verbose" in cmd.implicit_options
    assert "version" in cmd.implicit_options
    # implicit options must NOT bleed into user-defined options
    assert "help" not in cmd.options
    assert "verbose" not in cmd.options


def test_command_description_from_docstring():
    def run() -> None:
        """Short desc.

        Long desc.
        """

    cmd = Command("test", run)
    assert cmd.short_description == "Short desc."
    assert "Long desc." in cmd.description


def test_command_description_fallback():
    def run() -> None: ...
    cmd = Command("test", run)
    assert cmd.description == NO_DESC


def test_command_execute_returns_int(capsys):
    def run() -> None:
        print("ran")

    cmd = Command("test", run)
    result = cmd.execute([])
    assert result == 0
    assert "ran" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Command.print_short_help — smoke test (just ensure no crash)
# ---------------------------------------------------------------------------


def test_print_short_help_no_args(capsys):
    cmd = Command("test", lambda: 0)
    cmd.print_short_help()  # should not raise


def test_print_short_help_with_args(capsys):
    @command()
    def greet(name: str) -> None:
        """Greet someone."""

    greet.print_short_help()  # should not raise


def test_print_short_help_with_subcommands(capsys):
    root = Command("root", lambda: 0)
    root.subcommands["sub"] = Command("sub", lambda: 0)
    root.print_short_help()  # should not raise


# ---------------------------------------------------------------------------
# Command.print_long_help — smoke test
# ---------------------------------------------------------------------------


def test_print_long_help_no_args(capsys):
    cmd = Command("test", lambda: 0)
    cmd.print_long_help()


def test_print_long_help_with_args(capsys):
    @command()
    def greet(name: str) -> None:
        """Greet someone."""

    greet.print_long_help()


# ---------------------------------------------------------------------------
# Argument / Option dataclasses
# ---------------------------------------------------------------------------


def test_argument_short_description():
    arg = Argument("name", str, "First line.\nSecond line.")
    assert arg.short_description == "First line."


def test_option_short_description():
    opt = Option("verbose", bool, "First line.\nSecond line.")
    assert opt.short_description == "First line."


def test_option_default_any_type():
    opt = Option("count", int, "A count", 42)
    assert opt.default == 42

    opt2 = Option("items", list, "Items", [1, 2, 3])
    assert opt2.default == [1, 2, 3]
