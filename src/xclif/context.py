"""Dispatch context — exposes cascading framework state to user code."""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass


@dataclass(frozen=True)
class Context:
    """Read-only view of cascading framework state.

    Built-in properties provide typed access to implicit options::

        ctx = get_context()
        ctx.verbosity  # int (0–3)
        ctx.colors     # "always" | "never" | "auto"

    User-defined cascading options (marked with ``Cascade()``) are accessible
    via dict-style lookup::

        ctx["my_option"]
        ctx.get("my_option", default)
    """

    _data: dict

    @property
    def verbosity(self) -> int:
        """Verbosity level (0–3). Corresponds to ``-v`` / ``-vv`` / ``-vvv``."""
        return self._data.get("verbose", 0)

    @property
    def colors(self) -> str:
        """Color mode: ``"always"``, ``"never"``, or ``"auto"``."""
        return self._data.get("colors", "auto")

    def __getitem__(self, key: str) -> object:
        return self._data[key]

    def get(self, key: str, default: object = None) -> object:
        """Return the value for *key*, or *default* if not set."""
        return self._data.get(key, default)

    def __contains__(self, key: object) -> bool:
        return key in self._data


_context_var: ContextVar[Context] = ContextVar("xclif_context")


def get_context() -> Context:
    """Return the :class:`Context` for the current command dispatch.

    Raises :class:`RuntimeError` if called outside of command dispatch
    (i.e., no command is currently being executed by the framework).
    """
    try:
        return _context_var.get()
    except LookupError:
        raise RuntimeError(
            "get_context() called outside of command dispatch. "
            "It can only be used inside a command's run() function "
            "or code called from it."
        ) from None


def _set_context(ctx: Context) -> Token[Context]:
    """Set the dispatch context. Internal use only.

    Returns a token that must be passed to :func:`_reset_context` to restore
    the previous state.
    """
    return _context_var.set(ctx)


def _reset_context(token: Token[Context]) -> None:
    """Reset the dispatch context to its previous state. Internal use only."""
    _context_var.reset(token)
