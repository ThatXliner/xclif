"""Unit tests for xclif.Cli and the from_routes routing system."""

import importlib
import types
from pathlib import Path
from unittest.mock import patch

import pytest

from xclif import Cli, command
from xclif.command import Command


# ---------------------------------------------------------------------------
# Helpers to build minimal fake route modules in-memory
# ---------------------------------------------------------------------------


def _make_module(name: str, package: str, **attrs) -> types.ModuleType:
    mod = types.ModuleType(name)
    mod.__package__ = package
    for k, v in attrs.items():
        setattr(mod, k, v)
    return mod


# ---------------------------------------------------------------------------
# Cli construction
# ---------------------------------------------------------------------------


def test_cli_auto_adds_completions_command():
    root = Command("myapp", lambda: 0)
    cli = Cli(root_command=root)
    assert "completions" in cli.root_command.subcommands


def test_cli_completions_is_single_command_with_shell_arg():
    root = Command("myapp", lambda: 0)
    cli = Cli(root_command=root)
    comp = cli.root_command.subcommands["completions"]
    assert comp.subcommands == {}
    assert len(comp.arguments) == 1
    assert comp.arguments[0].choices == ["bash", "zsh", "fish"]


def test_cli_does_not_overwrite_user_completions_command(capsys):
    """A user-defined 'completions' subcommand is preserved (issue #61)."""
    root = Command("myapp", lambda: 0)
    user_completions = Command("completions", lambda: 42)
    root.subcommands["completions"] = user_completions

    cli = Cli(root_command=root)
    assert cli.root_command.subcommands["completions"] is user_completions


def test_cli_does_not_overwrite_user_mcp_command():
    """A user-defined 'mcp' subcommand is preserved (issue #61)."""
    root = Command("myapp", lambda: 0)
    user_mcp = Command("mcp", lambda: 7)
    root.subcommands["mcp"] = user_mcp

    cli = Cli(root_command=root)
    assert cli.root_command.subcommands["mcp"] is user_mcp


def test_cli_completions_command_flag_suppresses_injection():
    root = Command("myapp", lambda: 0)
    cli = Cli(root_command=root, completions_command=False)
    assert "completions" not in cli.root_command.subcommands


def test_cli_add_command_single_level():
    root = Command("myapp", lambda: 0)
    cli = Cli(root_command=root)
    sub = Command("sub", lambda: 0)
    cli.add_command(["sub"], sub)
    assert "sub" in cli.root_command.subcommands


def test_cli_add_command_nested():
    root = Command("myapp", lambda: 0)
    cli = Cli(root_command=root)
    deep = Command("set", lambda: 0)
    cli.add_command(["config", "set"], deep)
    assert "config" in cli.root_command.subcommands
    assert "set" in cli.root_command.subcommands["config"].subcommands


def test_cli_add_command_creates_intermediate_namespace():
    root = Command("myapp", lambda: 0)
    cli = Cli(root_command=root)
    cli.add_command(["a", "b", "c"], Command("c", lambda: 0))
    assert "a" in cli.root_command.subcommands
    assert "b" in cli.root_command.subcommands["a"].subcommands
    assert "c" in cli.root_command.subcommands["a"].subcommands["b"].subcommands


def test_cli_add_command_to_command_with_arguments_raises():
    @command()
    def root() -> None: ...

    @command()
    def intermediate(name: str) -> None: ...

    cli = Cli(root_command=root)
    cli.root_command.subcommands["intermediate"] = intermediate
    with pytest.raises(ValueError, match="Cannot add subcommand"):
        cli.add_command(["intermediate", "sub"], Command("sub", lambda: 0))


def test_cli_add_command_direct_to_root_with_arguments_raises():
    @command()
    def root() -> None: ...

    from xclif.definition import Argument

    cli = Cli(root_command=root)
    # Simulate root gaining arguments after construction (bypass __post_init__ guard)
    cli.root_command.arguments = [Argument("name", str, "")]
    with pytest.raises(ValueError, match="Cannot add subcommand"):
        cli.add_command(["sub"], Command("sub", lambda: 0))


def test_cli_construction_with_positional_root_skips_injection():
    """A root command with positional args is expressible; framework
    subcommands are silently skipped rather than raising (issue #61)."""

    @command()
    def root(name: str) -> None: ...

    cli = Cli(root_command=root)
    assert "completions" not in cli.root_command.subcommands
    assert "mcp" not in cli.root_command.subcommands
    # --version implicit option is still injected
    assert "version" in cli.root_command.implicit_options


# ---------------------------------------------------------------------------
# Cli.from_routes — error cases
# ---------------------------------------------------------------------------


def test_from_routes_no_command_raises():
    mod = _make_module("pkg.routes", "pkg.routes")
    with pytest.raises(ValueError, match="No commands found"):
        Cli.from_routes(mod)


def test_from_routes_multiple_commands_raises():
    @command()
    def a() -> None: ...

    @command()
    def b() -> None: ...

    mod = _make_module("pkg.routes", "pkg.routes", a=a, b=b)
    with pytest.raises(ValueError, match="Multiple commands found"):
        Cli.from_routes(mod)


def test_from_routes_no_package_raises():
    @command("myapp")
    def root() -> None: ...

    mod = _make_module("routes", None, root=root)
    with pytest.raises(ImportError, match="must be part of a package"):
        Cli.from_routes(mod)


# ---------------------------------------------------------------------------
# Cli.from_routes — greeter experiment (real package, integration-lite)
# ---------------------------------------------------------------------------


def test_from_routes_greeter_builds_cli():
    from greeter import routes

    cli = Cli.from_routes(routes)
    assert cli.root_command is not None
    # The root command is named after the routes module/package
    assert isinstance(cli.root_command, Command)


def test_from_routes_greeter_has_greet_subcommand():
    from greeter import routes

    cli = Cli.from_routes(routes)
    assert "greet" in cli.root_command.subcommands


def test_from_routes_greeter_has_config_namespace():
    from greeter import routes

    cli = Cli.from_routes(routes)
    assert "config" in cli.root_command.subcommands


def test_from_routes_greeter_config_has_set_and_get():
    from greeter import routes

    cli = Cli.from_routes(routes)
    config = cli.root_command.subcommands["config"]
    assert "set" in config.subcommands
    assert "get" in config.subcommands


def test_from_routes_skips_private_modules(tmp_path, monkeypatch):
    pkg = tmp_path / "private_routes_fixture"
    pkg.mkdir()
    (pkg / "__init__.py").write_text(
        "from xclif import command\n\n"
        "@command('app')\n"
        "def app() -> None: ...\n",
        encoding="utf-8",
    )
    (pkg / "public.py").write_text(
        "from xclif import command\n\n"
        "@command()\n"
        "def public() -> None: ...\n",
        encoding="utf-8",
    )
    (pkg / "_private.py").write_text(
        "from xclif import command\n\n"
        "@command()\n"
        "def private() -> None: ...\n",
        encoding="utf-8",
    )
    private_group = pkg / "_internal"
    private_group.mkdir()
    (private_group / "__init__.py").write_text("", encoding="utf-8")
    (private_group / "hidden.py").write_text(
        "from xclif import command\n\n"
        "@command()\n"
        "def hidden() -> None: ...\n",
        encoding="utf-8",
    )

    monkeypatch.syspath_prepend(str(tmp_path))
    importlib.invalidate_caches()
    routes = importlib.import_module("private_routes_fixture")

    cli = Cli.from_routes(routes)

    assert "public" in cli.root_command.subcommands
    assert "_private" not in cli.root_command.subcommands
    assert "_internal" not in cli.root_command.subcommands


def test_cli_default_env_prefix():
    root = Command("myapp", lambda: 0)
    cli = Cli(root_command=root)
    assert cli.env_prefix == "MYAPP"


def test_cli_custom_env_prefix():
    root = Command("myapp", lambda: 0)
    cli = Cli(root_command=root, env_prefix="CUSTOM")
    assert cli.env_prefix == "CUSTOM"


def test_cli_default_config_name():
    root = Command("myapp", lambda: 0)
    cli = Cli(root_command=root)
    assert cli.config_name == "myapp"


def test_cli_custom_config_name():
    root = Command("myapp", lambda: 0)
    cli = Cli(root_command=root, config_name="my-app-config")
    assert cli.config_name == "my-app-config"


def test_cli_loads_config_from_platformdirs(tmp_path):
    (tmp_path / "config.toml").write_text('greeting = "from_file"\n')

    root = Command("myapp", lambda: 0)
    with patch("platformdirs.user_config_dir", return_value=str(tmp_path)):
        cli = Cli(root_command=root)
    assert cli._config_data == {"greeting": "from_file"}


def test_cli_missing_config_file_is_empty(tmp_path):
    root = Command("myapp", lambda: 0)
    with patch("platformdirs.user_config_dir", return_value=str(tmp_path)):
        cli = Cli(root_command=root)
    assert cli._config_data == {}
