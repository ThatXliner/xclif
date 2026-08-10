"""Unit tests for auto-injected config subcommands."""

import json
from pathlib import Path
from unittest.mock import patch

import tomlkit

from xclif import Cli, WithConfig
from xclif.command import Command
from xclif.config_commands import make_config_command
from xclif.definition import _DefinitionOption


def _make_root_with_config_option():
    return Command(
        "myapp", lambda: 0,
        subcommands={
            "greet": Command(
                "greet", lambda greeting="hi": 0,
                options={"greeting": _DefinitionOption("greeting", str, "desc", "hi", config=WithConfig())},
            ),
        },
    )


def test_config_get_all(tmp_path, capsys):
    (tmp_path / "config.toml").write_text('greeting = "hello"\nname = "Alice"\n')
    cmd = make_config_command(tmp_path)
    result = cmd.subcommands["get"].execute([])
    assert result == 0
    out = capsys.readouterr().out
    assert "greeting" in out
    assert "hello" in out


def test_config_get_specific_key(tmp_path, capsys):
    (tmp_path / "config.toml").write_text('greeting = "hello"\nname = "Alice"\n')
    cmd = make_config_command(tmp_path)
    result = cmd.subcommands["get"].execute(["greeting"])
    assert result == 0
    out = capsys.readouterr().out
    assert "hello" in out


def test_config_get_missing_key(tmp_path, capsys):
    (tmp_path / "config.toml").write_text('greeting = "hello"\n')
    cmd = make_config_command(tmp_path)
    result = cmd.subcommands["get"].execute(["nonexistent"])
    assert result == 1


def test_config_get_no_file(tmp_path, capsys):
    cmd = make_config_command(tmp_path)
    result = cmd.subcommands["get"].execute([])
    assert result == 0
    out = capsys.readouterr().out
    assert "No config" in out or out.strip() == ""


def test_config_set_creates_toml(tmp_path, capsys):
    cmd = make_config_command(tmp_path)
    result = cmd.subcommands["set"].execute(["greeting", "howdy"])
    assert result == 0
    toml_path = tmp_path / "config.toml"
    assert toml_path.exists()
    data = tomlkit.loads(toml_path.read_text())
    assert data["greeting"] == "howdy"


def test_config_set_updates_existing_toml(tmp_path):
    toml_path = tmp_path / "config.toml"
    toml_path.write_text('name = "Alice"\n')
    cmd = make_config_command(tmp_path)
    cmd.subcommands["set"].execute(["greeting", "howdy"])
    data = tomlkit.loads(toml_path.read_text())
    assert data["greeting"] == "howdy"
    assert data["name"] == "Alice"


def test_config_set_writes_json_if_json_exists(tmp_path):
    json_path = tmp_path / "config.json"
    json_path.write_text(json.dumps({"name": "Alice"}))
    cmd = make_config_command(tmp_path)
    cmd.subcommands["set"].execute(["greeting", "howdy"])
    data = json.loads(json_path.read_text())
    assert data["greeting"] == "howdy"
    assert data["name"] == "Alice"


def test_config_path_default(tmp_path, capsys):
    """Shows default TOML path when no config file exists."""
    cmd = make_config_command(tmp_path)
    result = cmd.subcommands["path"].execute([])
    assert result == 0
    out = capsys.readouterr().out.strip()
    assert out == str(tmp_path / "config.toml")


def test_config_path_toml(tmp_path, capsys):
    """Shows existing TOML path."""
    (tmp_path / "config.toml").write_text('greeting = "hello"\n')
    cmd = make_config_command(tmp_path)
    result = cmd.subcommands["path"].execute([])
    assert result == 0
    out = capsys.readouterr().out.strip()
    assert out == str(tmp_path / "config.toml")


def test_config_path_json(tmp_path, capsys):
    """Shows existing JSON path."""
    (tmp_path / "config.json").write_text('{"greeting": "hello"}')
    cmd = make_config_command(tmp_path)
    result = cmd.subcommands["path"].execute([])
    assert result == 0
    out = capsys.readouterr().out.strip()
    assert out == str(tmp_path / "config.json")


def test_cli_auto_injects_config_when_with_config_exists(tmp_path):
    root = _make_root_with_config_option()
    with patch("platformdirs.user_config_dir", return_value=str(tmp_path)):
        cli = Cli(root_command=root)
    cli._finalize()
    assert "config" in cli.root_command.subcommands
    config_cmd = cli.root_command.subcommands["config"]
    assert "get" in config_cmd.subcommands
    assert "set" in config_cmd.subcommands
    assert "path" in config_cmd.subcommands
    assert "validate" in config_cmd.subcommands


def test_cli_skips_config_injection_when_already_exists(tmp_path):
    root = Command("myapp", lambda: 0, subcommands={
        "config": Command("config", lambda: 0),
        "greet": Command(
            "greet", lambda greeting="hi": 0,
            options={"greeting": _DefinitionOption("greeting", str, "desc", "hi", config=WithConfig())},
        ),
    })
    with patch("platformdirs.user_config_dir", return_value=str(tmp_path)):
        cli = Cli(root_command=root)
    cli._finalize()
    assert "get" not in cli.root_command.subcommands["config"].subcommands


def test_cli_no_config_injection_without_with_config(tmp_path):
    root = Command("myapp", lambda: 0, subcommands={
        "greet": Command("greet", lambda: 0),
    })
    with patch("platformdirs.user_config_dir", return_value=str(tmp_path)):
        cli = Cli(root_command=root)
    cli._finalize()
    assert "config" not in cli.root_command.subcommands
