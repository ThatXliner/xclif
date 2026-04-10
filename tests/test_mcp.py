"""Tests for MCP server integration."""
import inspect
import io
import contextlib

import pytest

from xclif.command import Command
from xclif.mcp import _collect_leaf_commands, _build_tool_wrapper


def make_cmd(name, run_fn, arguments=None, options=None, subcommands=None):
    cmd = Command(name, run_fn, arguments or [], options or {}, subcommands or {})
    return cmd


# --- _collect_leaf_commands ---

def test_collect_leaf_flat():
    def greet(): pass
    root = make_cmd("myapp", lambda: 0)
    leaf = make_cmd("greet", greet)
    root.subcommands["greet"] = leaf
    result = _collect_leaf_commands(root, "")
    assert result == [("greet", leaf)]


def test_collect_leaf_nested():
    root = make_cmd("myapp", lambda: 0)
    config = make_cmd("config", lambda: 0)
    get = make_cmd("get", lambda: 0)
    config.subcommands["get"] = get
    root.subcommands["config"] = config
    result = _collect_leaf_commands(root, "")
    assert result == [("config_get", get)]


def test_collect_skips_hidden():
    root = make_cmd("myapp", lambda: 0)
    leaf = make_cmd("greet", lambda: 0)
    completions = make_cmd("completions", lambda: 0)
    mcp_cmd = make_cmd("mcp", lambda: 0)
    root.subcommands["greet"] = leaf
    root.subcommands["completions"] = completions
    root.subcommands["mcp"] = mcp_cmd
    result = _collect_leaf_commands(root, "")
    assert result == [("greet", leaf)]


def test_collect_skips_aliases():
    root = make_cmd("myapp", lambda: 0)
    leaf = make_cmd("greet", lambda: 0)
    root.subcommands["greet"] = leaf
    root.subcommands["g"] = leaf  # alias — same object
    result = _collect_leaf_commands(root, "")
    assert len(result) == 1
    assert result[0][0] == "greet"


# --- _build_tool_wrapper ---

def test_wrapper_signature_str_arg():
    from xclif.definition import Argument
    def run(name): pass
    cmd = make_cmd("greet", run, arguments=[Argument("name", str, "A name")])
    wrapper = _build_tool_wrapper("greet", cmd)
    sig = inspect.signature(wrapper)
    params = list(sig.parameters.values())
    assert params[0].name == "name"
    assert params[0].annotation is str
    assert params[0].default is inspect.Parameter.empty


def test_wrapper_signature_option_with_default():
    from xclif.definition import Argument, _DefinitionOption
    def run(name, loud=False): pass
    cmd = make_cmd(
        "greet", run,
        arguments=[Argument("name", str, "A name")],
        options={"loud": _DefinitionOption("loud", bool, "Loud mode", default=False)},
    )
    wrapper = _build_tool_wrapper("greet", cmd)
    sig = inspect.signature(wrapper)
    params = list(sig.parameters.values())
    assert params[1].name == "loud"
    assert params[1].annotation is bool
    assert params[1].default is False


def test_wrapper_captures_stdout(capsys):
    from xclif.definition import Argument
    def run(name: str):
        print(f"hello {name}")
        return 0
    cmd = Command("greet", run, [Argument("name", str, "")], {})
    wrapper = _build_tool_wrapper("greet", cmd)
    result = wrapper(name="Alice")
    assert "hello Alice" in result


def test_wrapper_list_option():
    from xclif.definition import _DefinitionOption
    def run(tags: list = None): pass
    cmd = make_cmd(
        "tag", run,
        options={"tags": _DefinitionOption("tags", str, "Tags", default=None, is_list=True)},
    )
    wrapper = _build_tool_wrapper("tag", cmd)
    sig = inspect.signature(wrapper)
    params = list(sig.parameters.values())
    assert params[0].name == "tags"
    # list options get list annotation
    assert get_origin_safe(params[0].annotation) is list


def get_origin_safe(tp):
    from typing import get_origin
    return get_origin(tp)
