"""Unit tests for xclif.logging."""

from __future__ import annotations

import logging

import pytest

from xclif.command import Command
from xclif.logging import (
    RichLogHandler,
    configure_logging,
    get_logger,
    level_from_verbosity,
)


@pytest.fixture(autouse=True)
def restore_root_logging():
    root = logging.getLogger()
    original_level = root.level
    original_handlers = list(root.handlers)
    for handler in original_handlers:
        root.removeHandler(handler)
    yield
    for handler in list(root.handlers):
        root.removeHandler(handler)
        if getattr(handler, "_xclif_managed_handler", False):
            handler.close()
    root.setLevel(original_level)
    for handler in original_handlers:
        root.addHandler(handler)


def test_get_logger_returns_standard_logger():
    logger = get_logger("xclif.tests.logging")
    assert logger is logging.getLogger("xclif.tests.logging")


def test_level_from_verbosity_maps_to_standard_levels():
    assert level_from_verbosity(0) == logging.WARNING
    assert level_from_verbosity(1) == logging.INFO
    assert level_from_verbosity(2) == logging.DEBUG
    assert level_from_verbosity(3) == logging.NOTSET


def test_level_from_verbosity_clamps_values():
    assert level_from_verbosity(-10) == logging.WARNING
    assert level_from_verbosity(99) == logging.NOTSET


def test_configure_logging_accepts_explicit_level_name():
    root = logging.getLogger()

    configure_logging(level="ERROR", colors="never", force=True)

    assert root.level == logging.ERROR


def test_configure_logging_installs_lazy_rich_handler_without_importing_rich():
    root = logging.getLogger()
    handler = configure_logging(verbosity=1, colors="never", force=True)

    assert isinstance(handler, RichLogHandler)
    assert handler._inner is None
    assert root.level == logging.INFO
    assert root.handlers == [handler]


def test_configure_logging_enables_timestamps_at_max_verbosity():
    below = configure_logging(verbosity=2, colors="never", force=True)
    assert isinstance(below, RichLogHandler)
    assert below.show_time is False

    at_max = configure_logging(verbosity=3, colors="never", force=True)
    assert isinstance(at_max, RichLogHandler)
    assert at_max.show_time is True


def test_configure_logging_show_time_override_wins_over_verbosity():
    handler = configure_logging(
        verbosity=3, colors="never", force=True, show_time=False
    )
    assert isinstance(handler, RichLogHandler)
    assert handler.show_time is False


def test_configure_logging_reuses_single_managed_handler():
    root = logging.getLogger()

    first = configure_logging(verbosity=1, colors="never", force=True)
    second = configure_logging(verbosity=2, colors="never")

    assert first is not second
    assert isinstance(second, RichLogHandler)
    assert root.handlers == [second]
    assert root.level == logging.DEBUG


def test_configure_logging_respects_existing_handlers():
    root = logging.getLogger()
    existing = logging.NullHandler()
    root.addHandler(existing)

    handler = configure_logging(verbosity=1, colors="never")

    assert handler is None
    assert existing in root.handlers
    assert not any(
        getattr(handler, "_xclif_managed_handler", False)
        for handler in root.handlers
    )
    assert root.level == logging.INFO


def test_configure_logging_can_force_replace_existing_handlers():
    root = logging.getLogger()
    existing = logging.NullHandler()
    root.addHandler(existing)

    handler = configure_logging(verbosity=1, colors="never", force=True)

    assert isinstance(handler, RichLogHandler)
    assert root.handlers == [handler]
    assert root.level == logging.INFO


def test_configured_handler_emits_to_stderr(capsys):
    configure_logging(verbosity=0, colors="never", force=True)
    logger = logging.getLogger("xclif.tests.emit")

    logger.warning("careful now")

    captured = capsys.readouterr()
    assert "careful now" in captured.err
    assert captured.out == ""


def test_verbosity_controls_emitted_levels(capsys):
    configure_logging(verbosity=0, colors="never", force=True)
    logger = logging.getLogger("xclif.tests.levels")

    logger.info("hidden info")
    logger.warning("visible warning")

    captured = capsys.readouterr()
    assert "visible warning" in captured.err
    assert "hidden info" not in captured.err


def test_parser_configures_logging_from_context(monkeypatch):
    calls = []

    def fake_configure_logging(*, verbosity: int, colors: str) -> None:
        calls.append((verbosity, colors))

    monkeypatch.setattr("xclif.parser.configure_logging", fake_configure_logging)
    cmd = Command("test", lambda: 0)

    assert cmd.execute(["-vv", "--colors", "never"]) == 0
    assert calls == [(2, "never")]


def test_parser_does_not_configure_logging_for_help(monkeypatch):
    calls = []

    def fake_configure_logging(*, verbosity: int, colors: str) -> None:
        calls.append((verbosity, colors))

    monkeypatch.setattr("xclif.parser.configure_logging", fake_configure_logging)
    cmd = Command("test", lambda: 0)

    assert cmd.execute(["--help"]) == 0
    assert calls == []
