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


from xclif.context import get_context, _set_context, _reset_context


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
        _reset_context(token)


def test_context_reset():
    """After reset, get_context() raises again."""
    ctx = Context({"verbose": 1})
    token = _set_context(ctx)
    _reset_context(token)
    with pytest.raises(RuntimeError):
        get_context()


from xclif.command import Command, command


def test_get_context_during_dispatch():
    """get_context() works inside a command's run() function."""
    captured = {}

    @command("check")
    def _(name: str) -> None:
        """Check context."""
        ctx = get_context()
        captured["verbosity"] = ctx.verbosity
        captured["colors"] = ctx.colors

    cmd = _
    # -v -v gives verbosity 2
    cmd.execute(["-v", "-v", "hello"])
    assert captured["verbosity"] == 2
    assert captured["colors"] == "auto"


def test_verbosity_cascades_to_subcommand():
    """Verbosity set at parent cascades into subcommand's get_context()."""
    captured = {}

    @command("leaf")
    def leaf() -> None:
        """Leaf."""
        captured["verbosity"] = get_context().verbosity

    root = Command("root", lambda: 0)
    root.subcommands["leaf"] = leaf

    root.execute(["-v", "leaf"])
    assert captured["verbosity"] == 1


def test_get_context_unavailable_after_dispatch():
    """get_context() is unavailable after dispatch completes."""
    @command("noop")
    def _() -> None:
        """No-op."""
        pass

    cmd = _
    cmd.execute([])
    with pytest.raises(RuntimeError):
        get_context()
