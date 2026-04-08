"""Unit tests for xclif.command and xclif.definition."""

from typing import Annotated

import pytest

from xclif.command import Command, command, extract_parameters
from xclif.constants import NO_DESC
from xclif.definition import Argument, Option
from xclif import WithConfig
from xclif import Arg, Option as OptionMeta
from xclif.annotations import unwrap_param_metadata


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


def test_print_long_help_renders_markdown(capsys):
    @command()
    def greet(name: str) -> None:
        """Greet someone.

        This command supports **bold** and `code` in its help text.

        - Item one
        - Item two
        """

    greet.print_long_help()
    out = capsys.readouterr().out
    # The description should appear in the output (markdown rendered by Rich)
    assert "Greet someone." in out
    assert "Usage:" in out


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


def test_group_creates_namespace_subcommand():
    root = Command("root", lambda: 0)
    grp = root.group("config")

    assert "config" in root.subcommands
    assert isinstance(grp, Command)
    assert grp.name == "config"


def test_group_returns_command_for_chaining():
    root = Command("root", lambda: 0)
    config = root.group("config")

    @config.command()
    def set(key: str, value: str) -> None: ...

    assert "set" in config.subcommands
    assert "config" in root.subcommands


def test_chained_group_command_nesting():
    root = Command("root", lambda: 0)
    config = root.group("config")

    @config.command("get")
    def get_cmd(key: str) -> None: ...

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


# ---------------------------------------------------------------------------
# Argument / Option config field
# ---------------------------------------------------------------------------


def test_argument_config_field_default_none():
    arg = Argument("name", str, "desc")
    assert arg.config is None


def test_option_config_field_default_none():
    opt = Option("name", str, "desc")
    assert opt.config is None


def test_argument_config_field_set():
    wc = WithConfig()
    arg = Argument("name", str, "desc", config=wc)
    assert arg.config is wc
    assert isinstance(arg.config, WithConfig)


def test_option_config_field_set():
    wc = WithConfig()
    opt = Option("name", str, "desc", config=wc)
    assert opt.config is wc
    assert isinstance(opt.config, WithConfig)


# ---------------------------------------------------------------------------
# extract_parameters — WithConfig detection
# ---------------------------------------------------------------------------


def test_extract_params_with_config_option():
    def f(name: WithConfig[str] = "default") -> None: ...
    args, opts = extract_parameters(f)
    assert "name" in opts
    assert opts["name"].converter is str
    assert opts["name"].default == "default"
    assert opts["name"].config is not None
    assert opts["name"].config == WithConfig()


def test_extract_params_with_config_argument():
    def f(name: WithConfig[str]) -> None: ...
    args, opts = extract_parameters(f)
    assert len(args) == 1
    assert args[0].converter is str
    assert args[0].config is not None
    assert args[0].config == WithConfig()



def test_extract_params_without_config_has_none():
    def f(name: str = "default") -> None: ...
    args, opts = extract_parameters(f)
    assert opts["name"].config is None


def test_extract_params_with_config_int():
    def f(count: WithConfig[int] = 0) -> None: ...
    args, opts = extract_parameters(f)
    assert opts["count"].converter is int
    assert opts["count"].config is not None


# ---------------------------------------------------------------------------
# unwrap_param_metadata
# ---------------------------------------------------------------------------


def test_unwrap_param_metadata_plain_type():
    inner, arg_meta, opt_meta, with_config = unwrap_param_metadata(str)
    assert inner is str
    assert arg_meta is None
    assert opt_meta is None
    assert with_config is None

def test_unwrap_param_metadata_with_arg():
    a = Arg(description="A file", name="FILE")
    inner, arg_meta, opt_meta, with_config = unwrap_param_metadata(Annotated[str, a])
    assert inner is str and arg_meta is a and opt_meta is None and with_config is None

def test_unwrap_param_metadata_with_option():
    o = OptionMeta(description="Dry run", name="dry-run")
    inner, arg_meta, opt_meta, with_config = unwrap_param_metadata(Annotated[bool, o])
    assert inner is bool and arg_meta is None and opt_meta is o and with_config is None

def test_unwrap_param_metadata_with_config():
    from xclif import WithConfig
    inner, arg_meta, opt_meta, with_config = unwrap_param_metadata(Annotated[str, WithConfig()])
    assert inner is str and isinstance(with_config, WithConfig) and arg_meta is None and opt_meta is None

def test_unwrap_param_metadata_combined():
    from xclif import WithConfig
    a = Arg(description="desc")
    wc = WithConfig()
    inner, arg_meta, opt_meta, with_config = unwrap_param_metadata(Annotated[str, a, wc])
    assert inner is str and arg_meta is a and opt_meta is None and with_config is wc

def test_unwrap_param_metadata_option_and_withconfig():
    from xclif import WithConfig
    o = OptionMeta(description="desc")
    wc = WithConfig()
    inner, arg_meta, opt_meta, with_config = unwrap_param_metadata(Annotated[str, o, wc])
    assert inner is str and arg_meta is None and opt_meta is o and with_config is wc


# ---------------------------------------------------------------------------
# extract_parameters — Arg/Option metadata
# ---------------------------------------------------------------------------


def test_arg_description_from_metadata():
    def f(src: Annotated[str, Arg(description="Source file")]) -> None: ...
    args, opts = extract_parameters(f)
    assert args[0].description == "Source file"

def test_arg_name_override():
    def f(src: Annotated[str, Arg(name="SRC")]) -> None: ...
    args, opts = extract_parameters(f)
    assert args[0].name == "SRC"

def test_option_description_from_metadata():
    def f(dry_run: Annotated[bool, OptionMeta(description="Skip execution")] = False) -> None: ...
    args, opts = extract_parameters(f)
    assert opts["dry_run"].description == "Skip execution"

def test_option_name_override_cli_flag():
    def f(dry_run: Annotated[bool, OptionMeta(name="dry-run")] = False) -> None: ...
    args, opts = extract_parameters(f)
    assert "dry_run" in opts          # dict key stays as Python param name
    assert opts["dry_run"].name == "dry-run"  # internal name = CLI flag override

def test_option_metadata_on_argument_raises():
    def f(src: Annotated[str, OptionMeta(description="x")]) -> None: ...
    with pytest.raises(ValueError, match="Option\\(\\) used on argument"):
        extract_parameters(f)

def test_arg_metadata_on_option_raises():
    def f(src: Annotated[str, Arg(description="x")] = "default") -> None: ...
    with pytest.raises(ValueError, match="Arg\\(\\) used on option"):
        extract_parameters(f)

def test_arg_with_config_combined():
    from xclif import WithConfig
    def f(name: Annotated[str, Arg(description="A name"), WithConfig()]) -> None: ...
    args, opts = extract_parameters(f)
    assert args[0].description == "A name"
    assert args[0].config is not None

def test_option_with_config_combined():
    from xclif import WithConfig
    def f(greeting: Annotated[str, OptionMeta(description="Greeting"), WithConfig()] = "hi") -> None: ...
    args, opts = extract_parameters(f)
    assert opts["greeting"].description == "Greeting"
    assert opts["greeting"].config is not None


# ---------------------------------------------------------------------------
# Literal type support
# ---------------------------------------------------------------------------

from typing import Literal


def test_literal_argument_has_choices():
    def f(shell: Literal["bash", "zsh", "fish"]) -> None: ...
    args, opts = extract_parameters(f)
    assert len(args) == 1
    assert args[0].choices == ["bash", "zsh", "fish"]


def test_literal_argument_converter_validates():
    def f(shell: Literal["bash", "zsh", "fish"]) -> None: ...
    args, _ = extract_parameters(f)
    assert args[0].converter("bash") == "bash"
    with pytest.raises(ValueError):
        args[0].converter("nope")


def test_literal_option_has_choices():
    def f(shell: Literal["bash", "zsh"] = "bash") -> None: ...
    _, opts = extract_parameters(f)
    assert opts["shell"].choices == ["bash", "zsh"]
