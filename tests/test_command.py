"""Unit tests for xclif.command and xclif.definition."""

import pytest

from xclif import Cli
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
    # version is NOT an implicit option — it's injected by Cli on root only
    assert "version" not in cmd.implicit_options
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


# ---------------------------------------------------------------------------
# extract_parameters — variadic (*args)
# ---------------------------------------------------------------------------


def test_variadic_parameter_extracted():
    def f(*files: str) -> None: ...
    args, opts = extract_parameters(f)
    assert len(args) == 1
    assert args[0].variadic is True
    assert args[0].name == "files"
    assert args[0].converter is str


def test_variadic_with_fixed_params():
    def f(dest: str, *files: str) -> None: ...
    args, opts = extract_parameters(f)
    assert len(args) == 2
    assert args[0].variadic is False
    assert args[1].variadic is True


def test_variadic_no_annotation_raises():
    exec_globals: dict = {}
    exec("def f(*files) -> None: ...", exec_globals)
    with pytest.raises(ValueError, match="no type hint"):
        extract_parameters(exec_globals["f"])


# ---------------------------------------------------------------------------
# extract_parameters — auto short aliases
# ---------------------------------------------------------------------------


def test_auto_short_alias_generated():
    def f(name: str = "default") -> None: ...
    args, opts = extract_parameters(f)
    assert opts["name"].aliases == ["-n"]


def test_auto_alias_avoids_implicit_collision():
    """'-v' is taken by --verbose, '-h' by --help, so options starting
    with 'v' or 'h' should try a different char."""
    def f(value: str = "") -> None: ...
    args, opts = extract_parameters(f)
    # '-v' is taken by implicit --verbose, so should get '-a' (from 'value')
    # or no alias, depending on chars available
    for alias in opts["value"].aliases:
        assert alias != "-v"
        assert alias != "-h"


# ---------------------------------------------------------------------------
# extract_parameters — int/float/bool types now work
# ---------------------------------------------------------------------------


def test_int_parameter():
    def f(count: int) -> None: ...
    args, opts = extract_parameters(f)
    assert args[0].converter is int


def test_float_parameter():
    def f(rate: float) -> None: ...
    args, opts = extract_parameters(f)
    assert args[0].converter is float


def test_bool_option():
    def f(dry_run: bool = False) -> None: ...
    args, opts = extract_parameters(f)
    assert opts["dry_run"].converter is bool


# ---------------------------------------------------------------------------
# extract_parameters — list[T] types
# ---------------------------------------------------------------------------


def test_list_str_option():
    def f(tags: list[str] = []) -> None: ...
    args, opts = extract_parameters(f)
    assert "tags" in opts
    assert opts["tags"].is_list is True
    assert opts["tags"].converter is str
    assert opts["tags"].default == []


def test_list_int_option():
    def f(counts: list[int] = []) -> None: ...
    args, opts = extract_parameters(f)
    assert opts["counts"].is_list is True
    assert opts["counts"].converter is int


def test_list_float_option():
    def f(rates: list[float] = []) -> None: ...
    args, opts = extract_parameters(f)
    assert opts["rates"].is_list is True
    assert opts["rates"].converter is float


def test_non_list_option_is_not_list():
    def f(name: str = "default") -> None: ...
    args, opts = extract_parameters(f)
    assert opts["name"].is_list is False


# ---------------------------------------------------------------------------
# Command.command() and Command.group()
# ---------------------------------------------------------------------------


def test_command_method_registers_subcommand():
    root = Command("root", lambda: 0)

    @root.command()
    def greet(name: str) -> None: ...

    assert "greet" in root.subcommands


def test_command_method_uses_function_name():
    root = Command("root", lambda: 0)

    @root.command()
    def hello(name: str) -> None: ...

    assert "hello" in root.subcommands
    assert root.subcommands["hello"].name == "hello"


def test_command_method_uses_explicit_name():
    root = Command("root", lambda: 0)

    @root.command("hi")
    def hello(name: str) -> None: ...

    assert "hi" in root.subcommands
    assert "hello" not in root.subcommands


def test_command_method_returns_command():
    root = Command("root", lambda: 0)

    @root.command()
    def greet(name: str) -> None: ...

    assert isinstance(greet, Command)


def test_add_command_creates_namespace_subcommand():
    root = Command("root", lambda: 0)
    cli = Cli(root_command=root)

    @command()
    def set(key: str, value: str) -> None: ...

    cli.add_command(["config", "set"], set)

    assert "config" in root.subcommands
    config = root.subcommands["config"]
    assert isinstance(config, Command)
    assert config.name == "config"


def test_add_command_registers_nested_subcommand():
    root = Command("root", lambda: 0)
    cli = Cli(root_command=root)

    @command()
    def set(key: str, value: str) -> None: ...

    cli.add_command(["config", "set"], set)

    assert "set" in root.subcommands["config"].subcommands
    assert "config" in root.subcommands


def test_add_command_deep_nesting():
    root = Command("root", lambda: 0)
    cli = Cli(root_command=root)

    @command("get")
    def get_cmd(key: str) -> None: ...

    cli.add_command(["config", "get"], get_cmd)

    assert "config" in root.subcommands
    assert "get" in root.subcommands["config"].subcommands


def test_command_method_on_command_with_arguments_raises():
    root = Command("root", lambda: 0)
    # Add a positional argument directly
    from xclif.definition import Argument
    root.arguments.append(Argument("file", str, ""))

    with pytest.raises(ValueError, match="positional arguments"):
        @root.command()
        def sub() -> None: ...
