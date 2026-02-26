"""Unit tests for xclif.Cli and the from_routes routing system."""

import types

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
    def root(name: str) -> None: ...

    cli = Cli(root_command=root)
    with pytest.raises(ValueError, match="Cannot add subcommands"):
        cli.add_command(["name", "sub"], Command("sub", lambda: 0))


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
