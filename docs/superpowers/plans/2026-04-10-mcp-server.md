# MCP Server Auto-Exposure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose every leaf command in an xclif CLI as an MCP tool via a stdio server, auto-injected as a hidden `mcp` subcommand when the `mcp` package is installed.

**Architecture:** A new `src/xclif/mcp.py` module uses `FastMCP` from the `mcp` package. For each leaf command, a wrapper function is built with a dynamically-constructed `inspect.Signature` so `FastMCP` can derive the JSON Schema automatically. The `mcp` subcommand is injected in `Cli.__post_init__` only when `import mcp` succeeds (soft optional dependency). `Cli.serve_mcp()` calls `_finalize()` then starts the stdio server.

**Tech Stack:** Python 3.12+, `mcp>=1.27.0` (optional dep: `pip install xclif[mcp]`), `mcp.server.fastmcp.FastMCP`, `inspect.Signature`, `contextlib.redirect_stdout`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `src/xclif/mcp.py` | **Create** | All MCP logic: tree walk, wrapper building, server startup |
| `src/xclif/command.py` | **Modify** | Add `"mcp"` to `_AGENT_HIDDEN_SUBCOMMANDS` |
| `src/xclif/__init__.py` | **Modify** | Inject `mcp` subcommand in `__post_init__`; add `serve_mcp()` to `Cli` |
| `pyproject.toml` | **Already done** | `[project.optional-dependencies] mcp = ["mcp>=1.27.0"]` added by `uv add` |
| `tests/test_mcp.py` | **Create** | All MCP tests |

---

## Task 1: Hide `mcp` from agent help

**Files:**
- Modify: `src/xclif/command.py:15`

- [ ] **Step 1: Add `"mcp"` to `_AGENT_HIDDEN_SUBCOMMANDS`**

In `src/xclif/command.py`, line 15:

```python
_AGENT_HIDDEN_SUBCOMMANDS = {"completions", "mcp"}
```

- [ ] **Step 2: Run existing tests to confirm nothing broke**

```bash
uv run pytest tests/ -q
```

Expected: all tests pass.

- [ ] **Step 3: Commit**

```bash
git add src/xclif/command.py
git commit -m "feat(mcp): hide mcp subcommand from agent help"
```

---

## Task 2: Create `src/xclif/mcp.py` with tree-walking and wrapper building

**Files:**
- Create: `src/xclif/mcp.py`
- Create: `tests/test_mcp.py` (partial — tree walking + wrapper tests)

The key design: for each leaf command, we build a Python function whose `__signature__` matches the command's arguments (required, positional) and options (keyword with defaults). `FastMCP.add_tool` inspects that signature to derive the JSON Schema. The wrapper itself converts the incoming `**kwargs` back to an argv list and calls `cmd.execute(argv)`, capturing stdout.

Type mapping from xclif converter to Python annotation (for `inspect.Parameter`):
- `str` → `str`
- `int` → `int`
- `float` → `float`
- `bool` → `bool`
- converter with `__choices__` (Literal) → `str` (FastMCP will show string type; choices are enforced by xclif's parser)
- `is_list=True` option → `list[<inner_type>]` — derive inner type from `option.converter`

- [ ] **Step 1: Write failing tests for `_collect_leaf_commands` and `_build_tool_wrapper`**

Create `tests/test_mcp.py`:

```python
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
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/test_mcp.py -q
```

Expected: `ImportError: cannot import name '_collect_leaf_commands' from 'xclif.mcp'` (module doesn't exist yet).

- [ ] **Step 3: Create `src/xclif/mcp.py`**

```python
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
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cmd.execute(argv)
        return buf.getvalue()

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
```

- [ ] **Step 4: Run the tests**

```bash
uv run pytest tests/test_mcp.py -q
```

Expected: all tests in `test_mcp.py` pass.

- [ ] **Step 5: Run full test suite**

```bash
uv run pytest tests/ -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/xclif/mcp.py tests/test_mcp.py
git commit -m "feat(mcp): add mcp.py with leaf collection and tool wrapper building"
```

---

## Task 3: Inject `mcp` subcommand into `Cli` and add `serve_mcp()`

**Files:**
- Modify: `src/xclif/__init__.py`
- Test: `tests/test_mcp.py` (add injection tests)

- [ ] **Step 1: Write failing tests for Cli injection**

Append to `tests/test_mcp.py`:

```python
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
```

- [ ] **Step 2: Run to confirm they fail**

```bash
uv run pytest tests/test_mcp.py::test_mcp_subcommand_injected_when_mcp_installed tests/test_mcp.py::test_mcp_hidden_from_agent_help -q
```

Expected: FAIL — `mcp` not in `cli.root_command.subcommands`.

- [ ] **Step 3: Add mcp injection to `Cli.__post_init__` and `serve_mcp()` method**

In `src/xclif/__init__.py`, in `Cli.__post_init__`, after the `completions` injection block (around line 174), add:

```python
        # Add mcp subcommand (only if mcp optional dep is installed)
        try:
            import mcp as _mcp_pkg  # noqa: F401
            from xclif.mcp import make_mcp_command
            self.root_command._assert_no_arguments(adding="mcp")
            self.root_command.subcommands["mcp"] = make_mcp_command(self.root_command)
        except ImportError:
            pass  # mcp optional dep not installed; subcommand silently absent
```

Add `serve_mcp()` as a method on `Cli` (after `_finalize`, before `__call__`):

```python
    def serve_mcp(self) -> None:
        """Start an MCP stdio server exposing all leaf commands as tools.

        Requires the optional 'mcp' package: pip install xclif[mcp]
        """
        self._finalize()
        from xclif.mcp import serve_mcp_stdio
        serve_mcp_stdio(self.root_command)
```

- [ ] **Step 4: Run the new tests**

```bash
uv run pytest tests/test_mcp.py -q
```

Expected: all tests pass (skip `test_mcp_subcommand_absent_when_mcp_missing` if it's fragile due to module caching — that's acceptable).

- [ ] **Step 5: Run full test suite**

```bash
uv run pytest tests/ -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/xclif/__init__.py tests/test_mcp.py
git commit -m "feat(mcp): inject mcp subcommand in Cli and add serve_mcp()"
```

---

## Task 4: Integration test — tool dispatch end-to-end

**Files:**
- Test: `tests/test_mcp.py` (add integration tests)

These tests build a small command, register it with `FastMCP` via the wrapper, call the wrapper directly (simulating what `FastMCP` does when a tool is called), and assert stdout is captured correctly.

- [ ] **Step 1: Write integration tests**

Append to `tests/test_mcp.py`:

```python
# --- Integration: wrapper dispatch ---

def test_wrapper_dispatch_positional(capsys):
    """Wrapper correctly passes positional args to execute()."""
    from xclif.definition import Argument
    from xclif.mcp import _build_tool_wrapper

    outputs = []

    def run(name: str):
        outputs.append(name)
        return 0

    cmd = Command("greet", run, [Argument("name", str, "")], {})
    wrapper = _build_tool_wrapper("greet", cmd)
    result = wrapper(name="Alice")
    assert outputs == ["Alice"]
    assert isinstance(result, str)


def test_wrapper_dispatch_option(capsys):
    """Wrapper correctly passes options as --flag value."""
    from xclif.definition import Argument, _DefinitionOption
    from xclif.mcp import _build_tool_wrapper

    received = {}

    def run(name: str, loud: bool = False):
        received["name"] = name
        received["loud"] = loud
        return 0

    cmd = Command(
        "greet", run,
        [Argument("name", str, "")],
        {"loud": _DefinitionOption("loud", bool, "", default=False)},
    )
    wrapper = _build_tool_wrapper("greet", cmd)
    wrapper(name="Alice", loud=True)
    assert received == {"name": "Alice", "loud": True}


def test_wrapper_output_captured():
    """Wrapper returns stdout output as a string."""
    from xclif.definition import Argument
    from xclif.mcp import _build_tool_wrapper

    def run(name: str):
        print(f"Hello, {name}!")
        return 0

    cmd = Command("greet", run, [Argument("name", str, "")], {})
    wrapper = _build_tool_wrapper("greet", cmd)
    result = wrapper(name="World")
    assert result == "Hello, World!\n"


def test_wrapper_list_option_dispatch():
    """List options are passed as repeated --flag val."""
    from xclif.definition import _DefinitionOption
    from xclif.mcp import _build_tool_wrapper

    received = {}

    def run(tags: list = None):
        received["tags"] = tags
        return 0

    cmd = Command(
        "tag", run, [],
        {"tags": _DefinitionOption("tags", str, "", default=None, is_list=True)},
    )
    wrapper = _build_tool_wrapper("tag", cmd)
    wrapper(tags=["a", "b"])
    assert received["tags"] == ["a", "b"]


def test_serve_mcp_stdio_missing_dep(monkeypatch):
    """serve_mcp_stdio raises SystemExit with install instructions when mcp missing."""
    import builtins
    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "mcp.server.fastmcp" or name.startswith("mcp.server"):
            raise ImportError(f"mocked: no module named {name!r}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)

    from xclif.command import Command
    import xclif.mcp as mcp_module
    import importlib
    importlib.reload(mcp_module)
    from xclif.mcp import serve_mcp_stdio

    root = Command("myapp", lambda: 0)
    with pytest.raises(SystemExit) as exc_info:
        serve_mcp_stdio(root)
    assert "xclif[mcp]" in str(exc_info.value)
```

- [ ] **Step 2: Run integration tests**

```bash
uv run pytest tests/test_mcp.py -q
```

Expected: all tests pass.

- [ ] **Step 3: Run full test suite**

```bash
uv run pytest tests/ -q
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add tests/test_mcp.py
git commit -m "test(mcp): add integration tests for tool dispatch and soft-dep error"
```

---

## Task 5: Manual smoke test

This verifies the server actually starts and works with a real MCP client.

- [ ] **Step 1: Smoke test with the greeter example**

```bash
uv run python -c "
import sys
sys.path.insert(0, 'experiments/greeter')
import greeter.routes as routes
from xclif import Cli
cli = Cli.from_routes(routes)
print('mcp subcommand present:', 'mcp' in cli.root_command.subcommands)
print('leaf tools:')
from xclif.mcp import _collect_leaf_commands
for name, cmd in _collect_leaf_commands(cli.root_command, ''):
    print(f'  {name}: {cmd.short_description}')
"
```

Expected output (exact tool names depend on greeter routes):
```
mcp subcommand present: True
leaf tools:
  greet: ...
  ...
```

- [ ] **Step 2: Verify `myapp mcp --help` is hidden from agent help**

```bash
uv run python -c "
import sys
sys.path.insert(0, 'experiments/greeter')
import greeter.routes as routes
from xclif import Cli
cli = Cli.from_routes(routes)
cli.root_command.print_agent_help()
" | grep mcp
```

Expected: no output (mcp is hidden).

- [ ] **Step 3: Run full test suite one final time**

```bash
uv run pytest tests/ -q
```

Expected: all tests pass.

- [ ] **Step 4: Final commit**

```bash
git add -p  # review any remaining unstaged changes
git commit -m "feat(mcp): complete MCP stdio server integration (issue #54)"
```
