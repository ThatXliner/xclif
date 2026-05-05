"""Unit tests for xclif.command and xclif.definition."""

from typing import Annotated

import pytest

from xclif.command import Command, command, extract_parameters
from xclif.constants import NO_DESC
from xclif.definition import Argument, _DefinitionOption
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


def test_implicit_option_cli_name_override_raises():
    def f(foo: Annotated[str, OptionMeta(name="help")] = "bar") -> None: ...
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


def test_command_with_aliases():
    @command("checkout", "co")
    def _(name: str) -> None: ...

    assert _.name == "checkout"
    assert _.aliases == ["co"]


def test_command_with_multiple_aliases():
    @command("checkout", "co", "sw")
    def _(name: str) -> None: ...

    assert _.name == "checkout"
    assert _.aliases == ["co", "sw"]


def test_command_no_aliases_by_default():
    @command("checkout")
    def _(name: str) -> None: ...

    assert _.aliases == []


def test_command_no_args_no_aliases():
    @command()
    def greet() -> None: ...

    assert greet.aliases == []


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


def test_print_long_help_renders_markdown(capsys, monkeypatch):
    import sys
    from rich.console import Console
    monkeypatch.setattr(sys.modules["xclif.command"], "_get_console", lambda **kw: Console(force_terminal=True))

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
    opt = _DefinitionOption("verbose", bool, "First line.\nSecond line.")
    assert opt.short_description == "First line."


def test_option_default_any_type():
    opt = _DefinitionOption("count", int, "A count", 42)
    assert opt.default == 42

    opt2 = _DefinitionOption("items", list, "Items", [1, 2, 3])
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


def test_command_method_registers_aliases():
    root = Command("root", lambda: 0)

    @root.command("checkout", "co")
    def _(name: str) -> None: ...

    assert "checkout" in root.subcommands
    assert "co" in root.subcommands
    assert root.subcommands["checkout"] is root.subcommands["co"]


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
    opt = _DefinitionOption("name", str, "desc")
    assert opt.config is None


def test_argument_config_field_set():
    wc = WithConfig()
    arg = Argument("name", str, "desc", config=wc)
    assert arg.config is wc
    assert isinstance(arg.config, WithConfig)


def test_option_config_field_set():
    wc = WithConfig()
    opt = _DefinitionOption("name", str, "desc", config=wc)
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
    inner, arg_meta, opt_meta, with_config, cascade = unwrap_param_metadata(str)
    assert inner is str
    assert arg_meta is None
    assert opt_meta is None
    assert with_config is None
    assert cascade is False

def test_unwrap_param_metadata_with_arg():
    a = Arg(description="A file", name="FILE")
    inner, arg_meta, opt_meta, with_config, cascade = unwrap_param_metadata(Annotated[str, a])
    assert inner is str and arg_meta is a and opt_meta is None and with_config is None and cascade is False

def test_unwrap_param_metadata_with_option():
    o = OptionMeta(description="Dry run", name="dry-run")
    inner, arg_meta, opt_meta, with_config, cascade = unwrap_param_metadata(Annotated[bool, o])
    assert inner is bool and arg_meta is None and opt_meta is o and with_config is None and cascade is False

def test_unwrap_param_metadata_with_config():
    from xclif import WithConfig
    inner, arg_meta, opt_meta, with_config, cascade = unwrap_param_metadata(Annotated[str, WithConfig()])
    assert inner is str and isinstance(with_config, WithConfig) and arg_meta is None and opt_meta is None and cascade is False

def test_unwrap_param_metadata_combined():
    from xclif import WithConfig
    a = Arg(description="desc")
    wc = WithConfig()
    inner, arg_meta, opt_meta, with_config, cascade = unwrap_param_metadata(Annotated[str, a, wc])
    assert inner is str and arg_meta is a and opt_meta is None and with_config is wc and cascade is False

def test_unwrap_param_metadata_option_and_withconfig():
    from xclif import WithConfig
    o = OptionMeta(description="desc")
    wc = WithConfig()
    inner, arg_meta, opt_meta, with_config, cascade = unwrap_param_metadata(Annotated[str, o, wc])
    assert inner is str and arg_meta is None and opt_meta is o and with_config is wc and cascade is False


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


# ---------------------------------------------------------------------------
# Command.print_agent_help — agent-optimized output
# ---------------------------------------------------------------------------


def test_agent_help_leaf_command_no_options(capsys):
    """Leaf command with no user options prints name: description only."""
    cmd = Command("mytool", lambda: 0)
    cmd.run.__doc__ = "A simple tool."
    cmd.print_agent_help()
    out = capsys.readouterr().out
    assert out == "mytool: A simple tool.\n"


def test_agent_help_leaf_command_with_options(capsys):
    """Leaf command with user options lists them inline."""
    @command()
    def mytool(name: str = "", count: int = 3, dry_run: bool = False) -> None:
        """A tool with options."""

    mytool.print_agent_help()
    out = capsys.readouterr().out
    assert "mytool: A tool with options." in out
    assert "--name STR" in out
    assert '--count INT (default: 3)' in out
    assert "--dry-run" in out
    # Should NOT contain implicit framework options
    assert "--help" not in out
    assert "--colors" not in out


def test_agent_help_flattens_subcommands(capsys):
    """Subcommands are flattened with full path."""
    root = Command("app", lambda: 0)
    root.run.__doc__ = "My app."

    @command()
    def sub1() -> None:
        """First sub."""

    @command()
    def sub2(target: str = "") -> None:
        """Second sub."""

    root.subcommands["sub1"] = sub1
    root.subcommands["sub2"] = sub2

    root.print_agent_help()
    out = capsys.readouterr().out
    assert "app: My app." in out
    assert "sub1 - First sub." in out
    assert "sub2 - Second sub." in out
    assert "--target STR" in out


def test_agent_help_flattens_nested_subcommands(capsys):
    """Nested subcommands produce flattened paths like 'config get'."""
    root = Command("app", lambda: 0)
    root.run.__doc__ = "My app."

    group = Command("config", lambda: 0)
    group.run.__doc__ = "Manage config."

    @command()
    def get() -> None:
        """Print config."""

    @command()
    def set_cmd() -> None:
        """Set config."""

    group.subcommands["get"] = get
    group.subcommands["set"] = set_cmd
    root.subcommands["config"] = group

    root.print_agent_help()
    out = capsys.readouterr().out
    assert "config get - Print config." in out
    assert "config set" in out
    # The group itself should not appear as a separate line
    lines = [l for l in out.strip().split("\n") if l.startswith("config -")]
    assert lines == []


def test_agent_help_hides_completions_subcommand(capsys):
    """Framework subcommand 'completions' is filtered out."""
    root = Command("app", lambda: 0)
    root.run.__doc__ = "My app."

    @command()
    def real() -> None:
        """A real command."""

    completions = Command("completions", lambda: 0)
    completions.run.__doc__ = "Generate completions."

    root.subcommands["real"] = real
    root.subcommands["completions"] = completions

    root.print_agent_help()
    out = capsys.readouterr().out
    assert "real - A real command." in out
    assert "completions" not in out


def test_agent_help_shows_positional_arguments(capsys):
    """Positional arguments appear uppercased after the command name."""
    @command()
    def greet(name: str) -> None:
        """Greet someone."""

    greet.print_agent_help()
    out = capsys.readouterr().out
    assert out == "greet NAME: Greet someone.\n"


def test_agent_help_shows_variadic_arguments(capsys):
    """Variadic arguments show with trailing ellipsis."""
    @command()
    def cat(*files: str) -> None:
        """Concatenate files."""

    cat.print_agent_help()
    out = capsys.readouterr().out
    assert "cat FILES...: Concatenate files." in out


def test_agent_help_subcommand_with_arguments(capsys):
    """Subcommand arguments appear in the flattened listing."""
    root = Command("app", lambda: 0)
    root.run.__doc__ = "My app."

    @command()
    def greet(name: str, greeting: str = "Hello") -> None:
        """Greet someone."""

    root.subcommands["greet"] = greet
    root.print_agent_help()
    out = capsys.readouterr().out
    assert "greet NAME - Greet someone." in out
    assert "--greeting STR" in out


# ---------------------------------------------------------------------------
# TTY detection dispatch
# ---------------------------------------------------------------------------


def _patch_console_non_tty(monkeypatch):
    """Patch _get_console to report non-TTY."""
    import sys
    _cmd_module = sys.modules["xclif.command"]
    monkeypatch.setattr(_cmd_module, "_get_console", lambda **kw: type("C", (), {"is_terminal": False})())


def test_print_short_help_dispatches_agent_when_not_tty(capsys, monkeypatch):
    """print_short_help uses agent format when Console reports non-TTY."""
    _patch_console_non_tty(monkeypatch)
    root = Command("app", lambda: 0)
    root.run.__doc__ = "My app."

    @command()
    def sub() -> None:
        """A sub."""

    root.subcommands["sub"] = sub
    root.print_short_help()
    out = capsys.readouterr().out
    assert "app: My app." in out
    assert "sub - A sub." in out
    assert "[b]" not in out


def test_print_long_help_dispatches_agent_when_not_tty(capsys, monkeypatch):
    """print_long_help uses agent format when Console reports non-TTY."""
    _patch_console_non_tty(monkeypatch)

    @command()
    def mytool(name: str) -> None:
        """A tool."""

    mytool.print_long_help()
    out = capsys.readouterr().out
    assert "mytool NAME: A tool." in out
    assert "[b]" not in out
