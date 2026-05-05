"""Tests for xclif.plugins — entry-point-based subcommand discovery."""

import logging

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
