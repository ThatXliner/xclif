"""Unit tests for WithConfig conflict detection."""

import pytest

from xclif import WithConfig
from xclif.command import Command
from xclif.definition import Argument, _DefinitionOption
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
    """Same param name across commands + different types raises (same auto-env-var)."""
    cmd1 = Command("greet", lambda: None, options={
        "name": _DefinitionOption("name", str, "desc", config=WithConfig()),
    })
    cmd2 = Command("farewell", lambda: None, options={
        "name": _DefinitionOption("name", int, "desc", config=WithConfig()),
    })
    root = Command("app", lambda: 0, subcommands={"greet": cmd1, "farewell": cmd2})
    with pytest.raises(ValueError, match="WithConfig conflict"):
        check_with_config_conflicts(root, "APP")


def test_conflict_error_message_suggests_fix():
    """Error message includes actionable fix suggestion."""
    cmd1 = Command("greet", lambda: None, options={
        "name": _DefinitionOption("name", str, "desc", config=WithConfig()),
    })
    cmd2 = Command("farewell", lambda: None, options={
        "name": _DefinitionOption("name", int, "desc", config=WithConfig()),
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


def test_conflict_same_param_name_different_types():
    """Two sibling commands with the same param name but different WithConfig types conflict."""
    cmd1 = Command("a", lambda: None, options={
        "count": _DefinitionOption("count", str, "desc", config=WithConfig()),
    })
    cmd2 = Command("b", lambda: None, options={
        "count": _DefinitionOption("count", int, "desc", config=WithConfig()),
    })
    root = Command("app", lambda: 0, subcommands={"a": cmd1, "b": cmd2})
    with pytest.raises(ValueError, match="WithConfig conflict"):
        check_with_config_conflicts(root, "APP")
