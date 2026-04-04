"""Unit tests for WithConfig conflict detection."""

import pytest

from xclif import WithConfig
from xclif.command import Command
from xclif.definition import Argument, Option
from xclif.validation import check_with_config_conflicts


def test_no_conflicts_same_type():
    """Same config key + same type across commands is fine."""
    cmd1 = Command("greet", lambda name: None, arguments=[
        Argument("name", str, "desc", config=WithConfig()),
    ])
    cmd2 = Command("farewell", lambda name: None, arguments=[
        Argument("name", str, "desc", config=WithConfig()),
    ])
    root = Command("app", lambda: 0, subcommands={"greet": cmd1, "farewell": cmd2})
    check_with_config_conflicts(root, "APP")


def test_conflict_different_types_config_key():
    """Same config key + different types raises."""
    cmd1 = Command("greet", lambda name: None, arguments=[
        Argument("name", str, "desc", config=WithConfig()),
    ])
    cmd2 = Command("farewell", lambda name: None, arguments=[
        Argument("name", int, "desc", config=WithConfig()),
    ])
    root = Command("app", lambda: 0, subcommands={"greet": cmd1, "farewell": cmd2})
    with pytest.raises(ValueError, match="WithConfig conflict.*config key 'name'"):
        check_with_config_conflicts(root, "APP")


def test_conflict_different_types_env_var():
    """Same env var + different types raises."""
    cmd1 = Command("greet", lambda: None, options={
        "name": Option("name", str, "desc", config=WithConfig()),
    })
    cmd2 = Command("farewell", lambda: None, options={
        "name": Option("name", int, "desc", config=WithConfig()),
    })
    root = Command("app", lambda: 0, subcommands={"greet": cmd1, "farewell": cmd2})
    with pytest.raises(ValueError, match="WithConfig conflict.*env var 'APP_NAME'"):
        check_with_config_conflicts(root, "APP")


def test_conflict_custom_key_overlaps():
    """Two params with different names but same custom key + different types."""
    cmd1 = Command("a", lambda: None, options={
        "foo": Option("foo", str, "desc", config=WithConfig(key="shared")),
    })
    cmd2 = Command("b", lambda: None, options={
        "bar": Option("bar", int, "desc", config=WithConfig(key="shared")),
    })
    root = Command("app", lambda: 0, subcommands={"a": cmd1, "b": cmd2})
    with pytest.raises(ValueError, match="config key 'shared'"):
        check_with_config_conflicts(root, "APP")


def test_conflict_error_message_suggests_fix():
    """Error message includes actionable fix suggestion."""
    cmd1 = Command("greet", lambda: None, options={
        "name": Option("name", str, "desc", config=WithConfig()),
    })
    cmd2 = Command("farewell", lambda: None, options={
        "name": Option("name", int, "desc", config=WithConfig()),
    })
    root = Command("app", lambda: 0, subcommands={"greet": cmd1, "farewell": cmd2})
    with pytest.raises(ValueError, match="To fix"):
        check_with_config_conflicts(root, "APP")


def test_no_with_config_params_no_error():
    """Commands without WithConfig params don't trigger any checks."""
    cmd = Command("greet", lambda name: None, arguments=[
        Argument("name", str, "desc"),
    ])
    root = Command("app", lambda: 0, subcommands={"greet": cmd})
    check_with_config_conflicts(root, "APP")


def test_conflict_within_single_command():
    """Two options in the same command with conflicting keys."""
    cmd = Command("test", lambda: None, options={
        "name": Option("name", str, "desc", config=WithConfig(key="shared")),
        "count": Option("count", int, "desc", config=WithConfig(key="shared")),
    })
    root = Command("app", lambda: 0, subcommands={"test": cmd})
    with pytest.raises(ValueError, match="config key 'shared'"):
        check_with_config_conflicts(root, "APP")
