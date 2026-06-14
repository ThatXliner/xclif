"""Logging helpers for Xclif-powered CLIs.

This module builds on Python's standard :mod:`logging` package. It adds a
small Rich-backed default handler and a verbosity-to-level mapping that matches
Xclif's built-in ``-v`` / ``--verbose`` flag.
"""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from rich.console import Console

__all__ = [
    "LogProxy",
    "RichLogHandler",
    "configure_logging",
    "get_logger",
    "level_from_verbosity",
    "log",
]

_MANAGED_HANDLER_ATTR = "_xclif_managed_handler"
_DEFAULT_FORMATTER = logging.Formatter("%(message)s")
_VERBOSITY_LEVELS = (
    logging.WARNING,
    logging.INFO,
    logging.DEBUG,
    logging.NOTSET,
)


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a standard library logger.

    This is a tiny convenience wrapper around :func:`logging.getLogger`; Xclif
    intentionally does not introduce its own logger abstraction.
    """

    return logging.getLogger(name)


class LogProxy:
    """A ready-to-use logger that adopts the calling module's name.

    Unlike a logger captured at import time, this proxy resolves the caller's
    module on every call and forwards to ``logging.getLogger(<that module>)``.
    Records therefore carry the right source name (and ``file:line``) no matter
    which module imported ``log``, while still flowing through whatever
    :func:`configure_logging` installed on the root logger::

        from xclif import log

        log.info("Connecting...")   # logged as the calling module
    """

    __slots__ = ()

    def _log(self, level: int, msg: object, args: tuple, **kwargs: Any) -> None:
        # Caller stack: user -> debug()/info()/... -> _log() (here).
        # Frame 2 above this one is the user's call site.
        frame = sys._getframe(2)
        logger = logging.getLogger(frame.f_globals.get("__name__", "__main__"))
        if not logger.isEnabledFor(level):
            return
        # Skip both wrapper frames so file:line points at the user's call site.
        kwargs["stacklevel"] = kwargs.get("stacklevel", 1) + 2
        logger.log(level, msg, *args, **kwargs)

    def debug(self, msg: object, *args: Any, **kwargs: Any) -> None:
        self._log(logging.DEBUG, msg, args, **kwargs)

    def info(self, msg: object, *args: Any, **kwargs: Any) -> None:
        self._log(logging.INFO, msg, args, **kwargs)

    def warning(self, msg: object, *args: Any, **kwargs: Any) -> None:
        self._log(logging.WARNING, msg, args, **kwargs)

    def error(self, msg: object, *args: Any, **kwargs: Any) -> None:
        self._log(logging.ERROR, msg, args, **kwargs)

    def critical(self, msg: object, *args: Any, **kwargs: Any) -> None:
        self._log(logging.CRITICAL, msg, args, **kwargs)

    def exception(self, msg: object, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("exc_info", True)
        self._log(logging.ERROR, msg, args, **kwargs)

    def log(self, level: int, msg: object, *args: Any, **kwargs: Any) -> None:
        self._log(level, msg, args, **kwargs)


log = LogProxy()
"""The bundled Xclif logger. See :class:`LogProxy`."""


def level_from_verbosity(verbosity: int) -> int:
    """Map Xclif verbosity counts to standard logging levels.

    ``0`` shows warnings and errors, ``1`` enables info logs, ``2`` enables
    debug logs, and ``3`` enables every record that reaches the configured
    logger. Values outside the supported range are clamped.
    """

    index = max(0, min(int(verbosity), len(_VERBOSITY_LEVELS) - 1))
    return _VERBOSITY_LEVELS[index]


class RichLogHandler(logging.Handler):
    """A lazy wrapper around :class:`rich.logging.RichHandler`.

    Constructing Rich's handler imports Rich, which is nice for output but
    expensive on the hot path. This wrapper defers that import until a log
    record actually passes the configured level filters.
    """

    def __init__(
        self,
        level: int | str = logging.NOTSET,
        *,
        colors: str = "auto",
        console: "Console | None" = None,
        show_time: bool = False,
        show_level: bool = True,
        show_path: bool = False,
        markup: bool = False,
        rich_tracebacks: bool = True,
        tracebacks_show_locals: bool = False,
    ) -> None:
        super().__init__(level)
        _validate_colors(colors)
        self.colors = colors
        self.console = console
        self.show_time = show_time
        self.show_level = show_level
        self.show_path = show_path
        self.markup = markup
        self.rich_tracebacks = rich_tracebacks
        self.tracebacks_show_locals = tracebacks_show_locals
        self._inner: logging.Handler | None = None
        setattr(self, _MANAGED_HANDLER_ATTR, True)

    def setLevel(self, level: int | str) -> None:  # noqa: N802 - stdlib API
        super().setLevel(level)
        if self._inner is not None:
            self._inner.setLevel(level)

    def setFormatter(  # noqa: N802 - stdlib API
        self,
        fmt: logging.Formatter | None,
    ) -> None:
        super().setFormatter(fmt)
        if self._inner is not None:
            self._inner.setFormatter(fmt)

    def emit(self, record: logging.LogRecord) -> None:
        if self._inner is None:
            self._inner = self._make_inner_handler()
        self._inner.emit(record)

    def flush(self) -> None:
        if self._inner is not None:
            self._inner.flush()
        super().flush()

    def close(self) -> None:
        if self._inner is not None:
            self._inner.close()
        super().close()

    def _make_inner_handler(self) -> logging.Handler:
        from rich.logging import RichHandler

        handler = RichHandler(
            level=self.level,
            console=self.console or _make_console(self.colors),
            show_time=self.show_time,
            show_level=self.show_level,
            show_path=self.show_path,
            markup=self.markup,
            rich_tracebacks=self.rich_tracebacks,
            tracebacks_show_locals=self.tracebacks_show_locals,
        )
        handler.setFormatter(self.formatter or _DEFAULT_FORMATTER)
        return handler


def configure_logging(
    verbosity: int = 0,
    colors: str = "auto",
    *,
    logger: logging.Logger | str | None = None,
    level: int | str | None = None,
    force: bool = False,
    console: "Console | None" = None,
    show_time: bool | None = None,
    show_level: bool = True,
    show_path: bool | None = None,
    markup: bool = False,
    rich_tracebacks: bool = True,
) -> logging.Handler | None:
    """Configure standard logging for an Xclif command run.

    The root logger is used by default, so ordinary ``logging.getLogger`` calls
    in command code work without any Xclif-specific API. If logging has already
    been configured by the application, Xclif leaves existing handlers in place
    and only updates the logger level. Pass ``force=True`` to replace existing
    handlers with Xclif's Rich handler.

    Returns the installed handler, or ``None`` when existing non-Xclif handlers
    were respected.

    The Rich handler grows more detailed as *verbosity* rises: file/line
    locations appear at ``2`` (``-vv``) and timestamps at ``3`` (``-vvv``),
    matching Xclif's verbose-formatter behavior. The ``show_time`` and
    ``show_path`` arguments override that derivation when set explicitly.
    """

    _validate_colors(colors)
    target_logger = _resolve_logger(logger)
    resolved_level = (
        _coerce_level(level)
        if level is not None
        else level_from_verbosity(verbosity)
    )
    target_logger.setLevel(resolved_level)

    if force:
        _remove_handlers(target_logger, target_logger.handlers)
    else:
        managed_handlers = [
            handler
            for handler in target_logger.handlers
            if getattr(handler, _MANAGED_HANDLER_ATTR, False)
        ]
        if managed_handlers:
            _remove_handlers(target_logger, managed_handlers)
        elif target_logger.handlers:
            return None

    handler = RichLogHandler(
        resolved_level,
        colors=colors,
        console=console,
        show_time=verbosity >= 3 if show_time is None else show_time,
        show_level=show_level,
        show_path=verbosity >= 2 if show_path is None else show_path,
        markup=markup,
        rich_tracebacks=rich_tracebacks,
        tracebacks_show_locals=verbosity >= 3,
    )
    handler.setFormatter(_DEFAULT_FORMATTER)
    target_logger.addHandler(handler)
    return handler


def _resolve_logger(logger: logging.Logger | str | None) -> logging.Logger:
    if logger is None:
        return logging.getLogger()
    if isinstance(logger, str):
        return logging.getLogger(logger)
    return logger


def _remove_handlers(logger: logging.Logger, handlers: list[logging.Handler]) -> None:
    for handler in list(handlers):
        logger.removeHandler(handler)
        handler.close()


def _coerce_level(level: int | str) -> int:
    if isinstance(level, int):
        return level
    resolved = logging.getLevelNamesMapping().get(level.upper())
    if resolved is None:
        raise ValueError(f"Unknown logging level: {level!r}")
    return resolved


def _make_console(colors: str) -> "Console":
    from rich.console import Console

    if colors == "always":
        return Console(stderr=True, force_terminal=True)
    if colors == "never":
        return Console(stderr=True, no_color=True, highlight=False)
    return Console(stderr=True)


def _validate_colors(colors: str) -> None:
    if colors not in {"always", "never", "auto"}:
        raise ValueError("colors must be one of: always, never, auto")
