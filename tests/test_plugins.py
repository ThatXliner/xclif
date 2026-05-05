"""Tests for xclif.plugins — entry-point-based subcommand discovery."""

import logging
import os
import stat

from unittest.mock import MagicMock, patch

from xclif.command import Command


def test_discover_subcommands_returns_loaded_commands():
    """discover_subcommands loads entry points and returns name->Command dict."""
    mock_cmd = Command("myplugin", lambda: 0)
    mock_ep = MagicMock()
    mock_ep.name = "myplugin"
    mock_ep.load.return_value = mock_cmd

    with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
        from xclif.plugins import discover_subcommands
        result = discover_subcommands()

    assert result == {"myplugin": mock_cmd}


def test_discover_subcommands_skips_load_errors(caplog):
    """discover_subcommands logs a warning and skips entry points that fail to load."""
    caplog.set_level(logging.WARNING)
    mock_ep = MagicMock()
    mock_ep.name = "broken"
    mock_ep.load.side_effect = ImportError("missing dep")

    with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
        from xclif.plugins import discover_subcommands
        result = discover_subcommands()

    assert result == {}
    assert "broken" in caplog.text
    assert "missing dep" in caplog.text


def test_discover_subcommands_skips_non_command_objects(caplog):
    """discover_subcommands logs a warning and skips objects that aren't Command instances."""
    caplog.set_level(logging.WARNING)
    mock_ep = MagicMock()
    mock_ep.name = "notacmd"
    mock_ep.load.return_value = "not a command"

    with patch("importlib.metadata.entry_points", return_value=[mock_ep]):
        from xclif.plugins import discover_subcommands
        result = discover_subcommands()

    assert result == {}
    assert "notacmd" in caplog.text


def test_discover_subcommands_warns_on_duplicate_name(caplog):
    """discover_subcommands warns when two entry points register the same name."""
    caplog.set_level(logging.WARNING)
    mock_cmd1 = Command("plugin", lambda: 0)
    mock_ep1 = MagicMock()
    mock_ep1.name = "dupname"
    mock_ep1.load.return_value = mock_cmd1

    mock_ep2 = MagicMock()
    mock_ep2.name = "dupname"
    mock_ep2.load.return_value = Command("plugin", lambda: 0)

    with patch("importlib.metadata.entry_points", return_value=[mock_ep1, mock_ep2]):
        from xclif.plugins import discover_subcommands
        result = discover_subcommands()

    assert result == {"dupname": mock_cmd1}
    assert "dupname" in caplog.text


def test_discover_subcommands_returns_empty_dict_when_no_entry_points():
    """discover_subcommands returns empty dict when no entry points are registered."""
    with patch("importlib.metadata.entry_points", return_value=[]):
        from xclif.plugins import discover_subcommands
        result = discover_subcommands()

    assert result == {}


# ---------------------------------------------------------------------------
# discover_path_subcommands — Git-style PATH scanning
# ---------------------------------------------------------------------------


def test_discover_path_subcommands_finds_executables(tmp_path):
    """discover_path_subcommands finds xclif-* executables in PATH."""
    exe = tmp_path / "myapp-hello"
    exe.write_text("#!/bin/sh")
    exe.chmod(stat.S_IRWXU)

    with patch.dict(os.environ, {"PATH": str(tmp_path)}):
        from xclif.plugins import discover_path_subcommands
        result = discover_path_subcommands("myapp")

    assert "hello" in result
    assert result["hello"].name == "hello"
    assert result["hello"]._path_plugin_exe == str(exe)


def test_discover_path_subcommands_skips_non_executables(tmp_path):
    """discover_path_subcommands skips files that are not executable."""
    non_exe = tmp_path / "myapp-skipme"
    non_exe.write_text("not executable")

    with patch.dict(os.environ, {"PATH": str(tmp_path)}):
        from xclif.plugins import discover_path_subcommands
        result = discover_path_subcommands("myapp")

    assert result == {}


def test_discover_path_subcommands_skips_wrong_prefix(tmp_path):
    """discover_path_subcommands ignores files not matching {root_name}- prefix."""
    exe = tmp_path / "other-hello"
    exe.write_text("#!/bin/sh")
    exe.chmod(stat.S_IRWXU)

    with patch.dict(os.environ, {"PATH": str(tmp_path)}):
        from xclif.plugins import discover_path_subcommands
        result = discover_path_subcommands("myapp")

    assert result == {}


def test_discover_path_subcommands_first_in_path_wins(tmp_path):
    """When the same name appears in multiple PATH entries, the first wins."""
    dir_a = tmp_path / "a"
    dir_a.mkdir()
    exe_a = dir_a / "myapp-deploy"
    exe_a.write_text("#!/bin/sh")
    exe_a.chmod(stat.S_IRWXU)

    dir_b = tmp_path / "b"
    dir_b.mkdir()
    exe_b = dir_b / "myapp-deploy"
    exe_b.write_text("#!/bin/sh")
    exe_b.chmod(stat.S_IRWXU)

    path = f"{dir_a}{os.pathsep}{dir_b}"
    with patch.dict(os.environ, {"PATH": path}):
        from xclif.plugins import discover_path_subcommands
        result = discover_path_subcommands("myapp")

    assert "deploy" in result
    assert result["deploy"]._path_plugin_exe == str(exe_a)


def test_discover_path_subcommands_handles_no_path():
    """discover_path_subcommands returns empty dict when PATH is unset."""
    with patch.dict(os.environ, clear=True):
        from xclif.plugins import discover_path_subcommands
        result = discover_path_subcommands("myapp")

    assert result == {}


def test_discover_path_subcommands_marks_with_path_plugin_exe(tmp_path):
    """discovered command has _path_plugin_exe attribute for parser short-circuit."""
    exe = tmp_path / "myapp-deploy"
    exe.write_text("#!/bin/sh")
    exe.chmod(stat.S_IRWXU)

    with patch.dict(os.environ, {"PATH": str(tmp_path)}):
        from xclif.plugins import discover_path_subcommands
        result = discover_path_subcommands("myapp")

    assert hasattr(result["deploy"], "_path_plugin_exe")
