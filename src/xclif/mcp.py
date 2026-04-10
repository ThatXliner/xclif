"""MCP server integration for xclif.

Exposes all leaf commands of a CLI as MCP tools via a FastMCP stdio server.
Install the optional dependency to use: pip install xclif[mcp]
"""
from __future__ import annotations

import contextlib
import inspect
import io
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from xclif.command import Command

from xclif.command import _AGENT_HIDDEN_SUBCOMMANDS


def _collect_leaf_commands(cmd: "Command", prefix: str) -> list[tuple[str, "Command"]]:
    """Walk the command tree and return (tool_name, command) for every leaf.

    tool_name is the full command path joined by '_', e.g. 'config_get'.
    Hidden subcommands (completions, mcp) and alias entries are skipped.
    """
    results: list[tuple[str, "Command"]] = []
    seen_ids: set[int] = set()
    for name, sub in cmd.subcommands.items():
        if id(sub) in seen_ids:
            continue
        seen_ids.add(id(sub))
        if name in _AGENT_HIDDEN_SUBCOMMANDS:
            continue
        tool_name = f"{prefix}{name}" if prefix else name
        if sub.subcommands:
            results.extend(_collect_leaf_commands(sub, tool_name + "_"))
        else:
            results.append((tool_name, sub))
    return results


def _converter_to_annotation(converter, is_list: bool = False):
    """Map an xclif converter to a Python type annotation for inspect.Parameter."""
    _map = {str: str, int: int, float: float, bool: bool}
    base = _map.get(converter, str)  # Literal converters fall back to str
    if is_list:
        return list[base]
    return base


def _build_tool_wrapper(tool_name: str, cmd: "Command"):
    """Build a callable with a typed inspect.Signature for a leaf Command.

    FastMCP inspects the signature to derive the JSON Schema for the tool.
    The wrapper converts incoming kwargs back to an argv list, calls
    cmd.execute(), captures stdout, and returns it as a string.

    Note: stderr is captured and raised as RuntimeError on non-zero exit.
    This prevents xclif error output from bleeding into the MCP stdio transport.
    """
    params: list[inspect.Parameter] = []

    # Positional arguments → required parameters (no default)
    for arg in cmd.arguments:
        annotation = _converter_to_annotation(arg.converter)
        params.append(
            inspect.Parameter(
                arg.name,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=annotation,
            )
        )

    # Options → keyword parameters with defaults
    for name, opt in cmd.options.items():
        annotation = _converter_to_annotation(opt.converter, is_list=opt.is_list)
        params.append(
            inspect.Parameter(
                name,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                default=opt.default,
                annotation=annotation,
            )
        )

    def _wrapper(**kwargs: Any) -> str:
        argv = _kwargs_to_argv(cmd, kwargs)
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
            exit_code = cmd.execute(argv)
        if exit_code != 0:
            raise RuntimeError(stderr_buf.getvalue().strip() or f"Command failed with exit code {exit_code}")
        return stdout_buf.getvalue()

    _wrapper.__name__ = tool_name
    _wrapper.__signature__ = inspect.Signature(params)
    _wrapper.__annotations__ = {p.name: p.annotation for p in params}
    return _wrapper


def _kwargs_to_argv(cmd: "Command", kwargs: dict[str, Any]) -> list[str]:
    """Convert a kwargs dict from MCP back to an argv list for cmd.execute().

    Positional arguments are appended in declaration order.
    Options are emitted as --name value pairs (booleans: --name only when True;
    lists: repeated --name val for each element; missing values are omitted).
    """
    argv: list[str] = []

    # Positional arguments in declaration order
    for arg in cmd.arguments:
        value = kwargs.get(arg.name)
        if value is not None:
            if arg.variadic and isinstance(value, list):
                argv.extend(str(v) for v in value)
            else:
                argv.append(str(value))

    # Options
    for name, opt in cmd.options.items():
        value = kwargs.get(name)
        if value is None:
            continue
        flag = f"--{opt.name.replace('_', '-')}"
        if opt.converter is bool:
            if value:
                argv.append(flag)
        elif opt.is_list and isinstance(value, list):
            for item in value:
                argv.extend([flag, str(item)])
        else:
            argv.extend([flag, str(value)])

    return argv


def make_mcp_command(root: "Command") -> "Command":
    """Build the hidden 'mcp' subcommand that starts the stdio server."""
    from xclif.command import Command

    def mcp_run() -> int:
        """Start the MCP stdio server

        Starts an MCP stdio server exposing all commands as tools.
        """
        serve_mcp_stdio(root)
        return 0

    return Command("mcp", mcp_run)


def serve_mcp_stdio(root: "Command") -> None:
    """Start a FastMCP stdio server exposing all leaf commands as tools.

    Blocks until the server is stopped. Requires the 'mcp' package:
        pip install xclif[mcp]
    """
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        raise SystemExit(
            "The 'mcp' package is required for MCP server support.\n"
            "Install it with: pip install xclif[mcp]"
        )

    server = FastMCP(root.name)
    leaf_commands = _collect_leaf_commands(root, "")

    for tool_name, cmd in leaf_commands:
        wrapper = _build_tool_wrapper(tool_name, cmd)
        server.add_tool(wrapper, name=tool_name, description=cmd.short_description)

    server.run("stdio")
