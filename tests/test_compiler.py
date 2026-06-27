"""Tests for xclif.compiler and Cli.from_manifest."""

from __future__ import annotations

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


def test_compile_routes_skips_private_modules(tmp_path, monkeypatch):
    pkg = tmp_path / "private_compile_fixture"
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
    routes = importlib.import_module("private_compile_fixture")

    out = compile_routes(routes, output_dir=tmp_path)
    source = out.read_text(encoding="utf-8")

    assert "private_compile_fixture.public" in source
    assert "private_compile_fixture._private" not in source
    assert "private_compile_fixture._internal" not in source


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


def test_from_manifest_preserves_all_command_fields(tmp_path):
    """Manifest round-trip must preserve every field on Command objects,
    not just name/run/arguments/options.  Regression test: the compiler
    previously reconstructed Command(...) from only four fields, dropping
    subcommands, implicit_options, version, and any future fields."""
    from greeter import routes

    manifest_path = compile_routes(routes, output_dir=tmp_path)
    manifest = _load_manifest_from_path(manifest_path)

    cli_routes = Cli.from_routes(routes)
    cli_manifest = Cli.from_manifest(manifest)

    def _params_equal(params_r, params_m) -> bool:
        # Compare every field except ``converter`` by value, and the converter
        # by qualname — dynamically-generated commands (e.g. completions)
        # produce a new converter closure per Cli instance, so identity
        # comparison spuriously fails.
        if len(params_r) != len(params_m):
            return False
        for p_r, p_m in zip(params_r, params_m):
            rest_r = {k: v for k, v in vars(p_r).items() if k != "converter"}
            rest_m = {k: v for k, v in vars(p_m).items() if k != "converter"}
            if rest_r != rest_m:
                return False
            if p_r.converter.__qualname__ != p_m.converter.__qualname__:
                return False
        return True

    def _assert_commands_equal(cmd_r: Command, cmd_m: Command, path: str = "root"):
        assert cmd_r.name == cmd_m.name, f"{path}: name mismatch"
        # Use qualname comparison, not identity — dynamically-generated
        # commands (e.g. completions) produce new closures per Cli instance.
        assert cmd_r.run.__qualname__ == cmd_m.run.__qualname__, (
            f"{path}: run callable differs"
        )
        assert _params_equal(cmd_r.arguments, cmd_m.arguments), f"{path}: arguments differ"
        assert list(cmd_r.options) == list(cmd_m.options), f"{path}: option names differ"
        assert _params_equal(cmd_r.options.values(), cmd_m.options.values()), (
            f"{path}: options differ"
        )
        assert cmd_r.implicit_options == cmd_m.implicit_options, (
            f"{path}: implicit_options differ"
        )
        assert cmd_r.version == cmd_m.version, f"{path}: version differs"
        assert set(cmd_r.subcommands) == set(cmd_m.subcommands), (
            f"{path}: subcommand names differ"
        )
        for name in cmd_r.subcommands:
            _assert_commands_equal(
                cmd_r.subcommands[name],
                cmd_m.subcommands[name],
                f"{path}.{name}",
            )

    _assert_commands_equal(cli_routes.root_command, cli_manifest.root_command)


def test_from_manifest_preserves_imperative_subcommands(tmp_path):
    """Commands built via the imperative Command.command() API should
    survive the manifest round-trip."""
    import types

    root = Command("myapp", lambda: 0)

    @root.command("sub")
    def _(x: str) -> int:
        return 0

    # Build a minimal routes package with this root command
    routes = types.ModuleType("fake_routes")
    routes.__package__ = "fake_routes"
    routes.__path__ = [str(tmp_path / "fake_routes")]  # type: ignore[attr-defined]
    routes.__file__ = str(tmp_path / "fake_routes" / "__init__.py")
    routes.app = root  # type: ignore[attr-defined]

    # Create the package dir and register the module so the generated
    # manifest can import it
    pkg_dir = tmp_path / "fake_routes"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").touch()
    sys.modules["fake_routes"] = routes

    try:
        manifest_path = compile_routes(routes, output_dir=tmp_path)
        manifest = _load_manifest_from_path(manifest_path)
        cli = Cli.from_manifest(manifest)

        # The imperative subcommand "sub" should be present on the root
        assert "sub" in cli.root_command.subcommands
    finally:
        del sys.modules["fake_routes"]


# ---------------------------------------------------------------------------
# Cli.from_manifest — bad manifest
# ---------------------------------------------------------------------------


def test_from_manifest_version_explicit(tmp_path, capsys):
    """from_manifest(version=...) passes the version through to the CLI."""
    from greeter import routes

    manifest_path = compile_routes(routes, output_dir=tmp_path)
    manifest = _load_manifest_from_path(manifest_path)
    cli = Cli.from_manifest(manifest, version="4.5.6")
    assert cli.version == "4.5.6"
    result = cli.root_command.execute(["--version"])
    assert result == 0
    assert "4.5.6" in capsys.readouterr().out


def test_from_manifest_version_autodetect(tmp_path):
    """from_manifest() auto-detects version when none is provided."""
    from greeter import routes

    manifest_path = compile_routes(routes, output_dir=tmp_path)
    manifest = _load_manifest_from_path(manifest_path)

    cli_manifest = Cli.from_manifest(manifest)
    cli_routes = Cli.from_routes(routes)

    # Both paths should resolve the same version (or both None)
    assert cli_manifest.version == cli_routes.version


def test_from_manifest_missing_build_fn_raises(tmp_path):
    import types

    bad = types.ModuleType("bad_manifest")
    with pytest.raises(ImportError, match="_build_cli"):
        Cli.from_manifest(bad)


def test_from_manifest_threads_logging_flag(tmp_path):
    from greeter import routes

    manifest_path = compile_routes(routes, output_dir=tmp_path)
    manifest = _load_manifest_from_path(manifest_path)

    assert Cli.from_manifest(manifest).logging is True
    assert Cli.from_manifest(manifest, logging=False).logging is False


def test_from_manifest_rejects_logging_off_on_legacy_manifest():
    import types

    def _build_cli(version=None, env_prefix=None, config_name=None,
                   local_config=None, show_no_description=None):
        return Cli(root_command=Command("legacy", lambda: 0))

    legacy = types.ModuleType("legacy_manifest")
    legacy.__package__ = ""
    legacy._build_cli = _build_cli

    # Default (logging=True) still works against an old manifest.
    assert Cli.from_manifest(legacy).logging is True
    # Explicitly disabling logging fails loudly rather than silently ignoring.
    with pytest.raises(TypeError, match="predates the 'logging' option"):
        Cli.from_manifest(legacy, logging=False)
