"""Tests for xclif.compiler and Cli.from_manifest."""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path

import pytest

from xclif import Cli
from xclif.command import Command
from xclif.compiler import compile_routes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_manifest_from_path(path: Path) -> object:
    """Import a manifest .py file from an arbitrary path without installing it."""
    spec = importlib.util.spec_from_file_location("_xclif_manifest_test", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# ---------------------------------------------------------------------------
# compile_routes — output file
# ---------------------------------------------------------------------------


def test_compile_writes_manifest_file(tmp_path):
    from greeter import routes

    out = compile_routes(routes, output_dir=tmp_path)
    assert out.exists()
    assert out.name == "_xclif_manifest.py"


def test_compile_manifest_is_valid_python(tmp_path):
    from greeter import routes

    out = compile_routes(routes, output_dir=tmp_path)
    source = out.read_text()
    compile(source, str(out), "exec")  # raises SyntaxError if invalid


def test_compile_manifest_contains_build_cli(tmp_path):
    from greeter import routes

    out = compile_routes(routes, output_dir=tmp_path)
    source = out.read_text()
    assert "def _build_cli(" in source


def test_compile_manifest_imports_all_route_modules(tmp_path):
    from greeter import routes

    out = compile_routes(routes, output_dir=tmp_path)
    source = out.read_text()
    assert "greeter.routes.greet" in source
    assert "greeter.routes.config" in source
    assert "greeter.routes.config.set" in source
    assert "greeter.routes.config.read" in source  # module is named read.py even though command is "get"


# ---------------------------------------------------------------------------
# compile_routes — error cases
# ---------------------------------------------------------------------------


def test_compile_no_command_raises(tmp_path):
    import types

    mod = types.ModuleType("fake.routes")
    mod.__package__ = "fake.routes"
    mod.__path__ = []  # type: ignore[attr-defined]
    mod.__file__ = str(tmp_path / "__init__.py")
    (tmp_path / "__init__.py").touch()

    with pytest.raises(ValueError, match="No commands found"):
        compile_routes(mod, output_dir=tmp_path)


# ---------------------------------------------------------------------------
# Cli.from_manifest — round-trip: same tree as from_routes
# ---------------------------------------------------------------------------


def test_from_manifest_builds_cli(tmp_path):
    from greeter import routes

    manifest_path = compile_routes(routes, output_dir=tmp_path)
    manifest = _load_manifest_from_path(manifest_path)
    cli = Cli.from_manifest(manifest)
    assert isinstance(cli, Cli)
    assert isinstance(cli.root_command, Command)


def test_from_manifest_root_command_name_matches(tmp_path):
    from greeter import routes

    manifest_path = compile_routes(routes, output_dir=tmp_path)
    manifest = _load_manifest_from_path(manifest_path)

    cli_routes = Cli.from_routes(routes)
    cli_manifest = Cli.from_manifest(manifest)

    assert cli_manifest.root_command.name == cli_routes.root_command.name


def test_from_manifest_has_greet_subcommand(tmp_path):
    from greeter import routes

    manifest_path = compile_routes(routes, output_dir=tmp_path)
    manifest = _load_manifest_from_path(manifest_path)
    cli = Cli.from_manifest(manifest)
    assert "greet" in cli.root_command.subcommands


def test_from_manifest_has_config_namespace(tmp_path):
    from greeter import routes

    manifest_path = compile_routes(routes, output_dir=tmp_path)
    manifest = _load_manifest_from_path(manifest_path)
    cli = Cli.from_manifest(manifest)
    assert "config" in cli.root_command.subcommands


def test_from_manifest_config_has_set_and_get(tmp_path):
    from greeter import routes

    manifest_path = compile_routes(routes, output_dir=tmp_path)
    manifest = _load_manifest_from_path(manifest_path)
    cli = Cli.from_manifest(manifest)
    config = cli.root_command.subcommands["config"]
    assert "set" in config.subcommands
    assert "get" in config.subcommands


def test_from_manifest_subcommand_signatures_match(tmp_path):
    """Arguments and options of each subcommand match from_routes output."""
    from greeter import routes

    manifest_path = compile_routes(routes, output_dir=tmp_path)
    manifest = _load_manifest_from_path(manifest_path)

    cli_routes = Cli.from_routes(routes)
    cli_manifest = Cli.from_manifest(manifest)

    greet_r = cli_routes.root_command.subcommands["greet"]
    greet_m = cli_manifest.root_command.subcommands["greet"]

    assert [a.name for a in greet_r.arguments] == [a.name for a in greet_m.arguments]
    assert list(greet_r.options.keys()) == list(greet_m.options.keys())


# ---------------------------------------------------------------------------
# Cli.from_manifest — bad manifest
# ---------------------------------------------------------------------------


def test_from_manifest_missing_build_fn_raises(tmp_path):
    import types

    bad = types.ModuleType("bad_manifest")
    with pytest.raises(ImportError, match="_build_cli"):
        Cli.from_manifest(bad)
