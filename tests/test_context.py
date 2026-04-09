"""Unit tests for xclif.context."""

import pytest

from xclif.context import Context


def test_verbosity_default():
    ctx = Context({})
    assert ctx.verbosity == 0


def test_verbosity_from_data():
    ctx = Context({"verbose": 2})
    assert ctx.verbosity == 2


def test_colors_default():
    ctx = Context({})
    assert ctx.colors == "auto"


def test_colors_from_data():
    ctx = Context({"colors": "never"})
    assert ctx.colors == "never"


def test_getitem():
    ctx = Context({"verbose": 1, "custom": "val"})
    assert ctx["custom"] == "val"
    assert ctx["verbose"] == 1


def test_getitem_missing_raises():
    ctx = Context({})
    with pytest.raises(KeyError):
        ctx["nonexistent"]


def test_get_with_default():
    ctx = Context({})
    assert ctx.get("missing", 42) == 42


def test_get_without_default():
    ctx = Context({})
    assert ctx.get("missing") is None


def test_contains():
    ctx = Context({"verbose": 1})
    assert "verbose" in ctx
    assert "missing" not in ctx


from xclif.context import get_context, _set_context


def test_get_context_outside_dispatch():
    """get_context() raises RuntimeError when no dispatch is active."""
    with pytest.raises(RuntimeError, match="outside of command dispatch"):
        get_context()


def test_set_and_get_context():
    """get_context() returns the Context set by _set_context()."""
    ctx = Context({"verbose": 2})
    token = _set_context(ctx)
    try:
        assert get_context() is ctx
        assert get_context().verbosity == 2
    finally:
        _set_context(None, token)


def test_context_reset():
    """After reset, get_context() raises again."""
    ctx = Context({"verbose": 1})
    token = _set_context(ctx)
    _set_context(None, token)
    with pytest.raises(RuntimeError):
        get_context()
