"""Tests for MCP server integration."""
import inspect

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


def test_wrapper_captures_stdout():
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


# --- Cli injection ---

def test_mcp_subcommand_injected_when_mcp_installed():
    """When mcp package is available, Cli injects mcp subcommand."""
    pytest.importorskip("mcp")  # skip if mcp not installed
    from xclif import Cli
    from xclif.command import Command

    def root_run(): pass
    root = Command("myapp", root_run)
    cli = Cli(root_command=root)
    assert "mcp" in cli.root_command.subcommands


def test_mcp_subcommand_absent_when_mcp_missing(monkeypatch):
    """When mcp package is not importable, Cli silently skips injection."""
    import builtins
    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "mcp" or name.startswith("mcp."):
            raise ImportError(f"mocked: no module named {name!r}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)

    # Re-import Cli with mcp blocked — need to reload the module
    import importlib
    import xclif
    importlib.reload(xclif)
    from xclif import Cli
    from xclif.command import Command

    def root_run(): pass
    root = Command("myapp", root_run)
    cli = Cli(root_command=root)
    assert "mcp" not in cli.root_command.subcommands


def test_mcp_hidden_from_agent_help(capsys):
    """mcp subcommand does not appear in agent help output."""
    pytest.importorskip("mcp")
    from xclif import Cli
    from xclif.command import Command

    def root_run():
        """My app."""
    root = Command("myapp", root_run)

    def greet(name: str):
        """Greet someone."""
    from xclif.command import command
    greet_cmd = command("greet")(greet)
    root.subcommands["greet"] = greet_cmd

    cli = Cli(root_command=root)
    cli.root_command.print_agent_help()
    captured = capsys.readouterr()
    assert "mcp" not in captured.out
    assert "greet" in captured.out


def test_serve_mcp_stdio_missing_dep_error(monkeypatch):
    """serve_mcp_stdio raises SystemExit with xclif[mcp] instructions when mcp missing."""
    import builtins
    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "mcp.server.fastmcp":
            raise ImportError(f"mocked: no module named {name!r}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)

    import importlib
    import xclif.mcp as mcp_module
    importlib.reload(mcp_module)

    from xclif.command import Command
    root = Command("myapp", lambda: 0)
    with pytest.raises(SystemExit) as exc_info:
        mcp_module.serve_mcp_stdio(root)
    assert "xclif[mcp]" in str(exc_info.value)


def test_cli_serve_mcp_missing_dep_raises(monkeypatch):
    """Cli.serve_mcp() raises SystemExit with install instructions when mcp missing."""
    pytest.importorskip("mcp")  # only run if mcp is installed (we'll mock it out)
    import builtins
    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "mcp.server.fastmcp":
            raise ImportError(f"mocked: no module named {name!r}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)

    from xclif import Cli
    from xclif.command import Command

    def root_run(): pass
    root = Command("myapp", root_run)
    cli = Cli(root_command=root)

    import xclif.mcp as mcp_module
    import importlib
    importlib.reload(mcp_module)

    with pytest.raises(SystemExit) as exc_info:
        cli.serve_mcp()
    assert "xclif[mcp]" in str(exc_info.value)
