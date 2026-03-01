"""Integration tests for the greeter example.

These tests exercise the full stack: routing, parsing, and execution.
The greeter CLI has:
  - greeter               (root — prints help when called with no args)
  - greeter greet         (--name: str, --template: str = "Hello, {}!")
  - greeter config        (namespace)
  - greeter config set    (--name: str, --template: str)
  - greeter config get
"""

import json
import pytest

from greeter import routes
from xclif import Cli


@pytest.fixture(scope="module")
def cli():
    return Cli.from_routes(routes)


@pytest.fixture(scope="module")
def root(cli):
    return cli.root_command


# ---------------------------------------------------------------------------
# Root command
# ---------------------------------------------------------------------------


def test_root_executes(root, capsys):
    # The root has subcommands, so invoking it with no args triggers short help.
    result = root.execute([])
    assert result == 0
    assert capsys.readouterr().out != ""


def test_root_help_returns_zero(root, capsys):
    result = root.execute(["--help"])
    assert result == 0


# ---------------------------------------------------------------------------
# greeter greet
# ---------------------------------------------------------------------------


def test_greet_with_name_option(root, capsys, tmp_path, monkeypatch):
    import greeter.routes.greet as greet_mod
    monkeypatch.setattr(greet_mod, "_CONFIG_PATH", str(tmp_path / "no_config.json"))
    result = root.execute(["greet", "--name", "Alice"])
    assert result == 0
    assert "Alice" in capsys.readouterr().out


def test_greet_default_template(root, capsys, tmp_path, monkeypatch):
    import greeter.routes.greet as greet_mod
    monkeypatch.setattr(greet_mod, "_CONFIG_PATH", str(tmp_path / "no_config.json"))
    root.execute(["greet", "--name", "Alice"])
    assert "Hello, Alice!" in capsys.readouterr().out


def test_greet_custom_template(root, capsys, tmp_path, monkeypatch):
    import greeter.routes.greet as greet_mod
    monkeypatch.setattr(greet_mod, "_CONFIG_PATH", str(tmp_path / "no_config.json"))
    root.execute(["greet", "--name", "Alice", "--template", "Hi, {}!"])
    assert "Hi, Alice!" in capsys.readouterr().out


def test_greet_no_name_prints_error(root, capsys, tmp_path, monkeypatch):
    # Patch config path to a non-existent file so no stored name is found.
    import greeter.routes.greet as greet_mod
    monkeypatch.setattr(greet_mod, "_CONFIG_PATH", str(tmp_path / "no_config.json"))
    result = root.execute(["greet"])
    assert result == 0
    assert "Error" in capsys.readouterr().out


def test_greet_help_returns_zero(root, capsys):
    result = root.execute(["greet", "--help"])
    assert result == 0


def test_greet_unknown_option_returns_error(root, capsys):
    result = root.execute(["greet", "--nonexistent"])
    assert result == 2
    assert "Unknown option" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# greeter config (namespace — no-arg subcommand group)
# ---------------------------------------------------------------------------


def test_config_namespace_help_returns_zero(root, capsys):
    result = root.execute(["config", "--help"])
    assert result == 0


def test_config_set_executes(root, tmp_path, monkeypatch):
    import greeter.routes.config.set as set_mod
    monkeypatch.setattr(set_mod, "_CONFIG_PATH", str(tmp_path / "config.json"))
    result = root.execute(["config", "set", "--name", "Bob"])
    assert result == 0
    assert json.loads((tmp_path / "config.json").read_text())["name"] == "Bob"


def test_config_get_executes(root, capsys, tmp_path, monkeypatch):
    import greeter.routes.config.read as read_mod
    monkeypatch.setattr(read_mod, "_CONFIG_PATH", str(tmp_path / "no_config.json"))
    result = root.execute(["config", "get"])
    assert result == 0
    out = capsys.readouterr().out
    assert "No config file found" in out


def test_config_set_then_get_roundtrip(root, capsys, tmp_path, monkeypatch):
    import greeter.routes.config.set as set_mod
    import greeter.routes.config.read as read_mod
    cfg_path = str(tmp_path / "config.json")
    monkeypatch.setattr(set_mod, "_CONFIG_PATH", cfg_path)
    monkeypatch.setattr(read_mod, "_CONFIG_PATH", cfg_path)

    root.execute(["config", "set", "--name", "Alice", "--template", "Hey, {}!"])
    root.execute(["config", "get"])
    out = capsys.readouterr().out
    assert "Alice" in out
    assert "Hey, {}!" in out


def test_greet_uses_stored_config(root, capsys, tmp_path, monkeypatch):
    import greeter.routes.config.set as set_mod
    import greeter.routes.greet as greet_mod
    cfg_path = str(tmp_path / "config.json")
    monkeypatch.setattr(set_mod, "_CONFIG_PATH", cfg_path)
    monkeypatch.setattr(greet_mod, "_CONFIG_PATH", cfg_path)

    root.execute(["config", "set", "--name", "Carol", "--template", "Howdy, {}!"])
    capsys.readouterr()  # discard "Config saved" output
    root.execute(["greet"])
    assert "Howdy, Carol!" in capsys.readouterr().out


def test_unknown_subcommand_returns_error(root, capsys):
    result = root.execute(["doesnotexist"])
    assert result == 2
    assert "Unknown" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# Completions (auto-added by Cli)
# ---------------------------------------------------------------------------


def test_completions_subcommand_exists(cli):
    assert "completions" in cli.root_command.subcommands


def test_completions_executes(cli, capsys):
    result = cli.root_command.execute(["completions"])
    assert result == 0


# ---------------------------------------------------------------------------
# Misc / regression
# ---------------------------------------------------------------------------


def test_root_help_short_flag(root, capsys):
    result = root.execute(["-h"])
    assert result == 0
    assert capsys.readouterr().out != ""


def test_greet_help_short_flag(root, capsys):
    result = root.execute(["greet", "-h"])
    assert result == 0


def test_verbose_before_subcommand(root, capsys, tmp_path, monkeypatch):
    import greeter.routes.greet as greet_mod
    monkeypatch.setattr(greet_mod, "_CONFIG_PATH", str(tmp_path / "no_config.json"))
    result = root.execute(["-v", "greet", "--name", "Alice"])
    assert result == 0
    assert "Alice" in capsys.readouterr().out


def test_version_on_root(cli, capsys):
    result = cli.root_command.execute(["--version"])
    assert result == 0


def test_version_not_on_subcommand(root, capsys):
    """--version should not be recognized on subcommands."""
    result = root.execute(["greet", "--version"])
    assert result == 2
    assert "Unknown option" in capsys.readouterr().err
