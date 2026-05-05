# MCP Server Auto-Exposure (Issue #54)

## Summary

Xclif exposes a CLI's command tree as an MCP (Model Context Protocol) stdio server with zero boilerplate. Every leaf command becomes an MCP tool. A hidden `mcp` subcommand is auto-injected by `Cli.__post_init__`, mirroring the existing `completions` injection pattern.

Transport: stdio only. SSE/HTTP is a future stretch goal.

---

## Architecture

A new module `src/xclif/mcp.py` contains all MCP-related logic. No changes to `Command` are needed — all introspection uses the existing `Command.arguments` and `Command.options` fields.

The `mcp` package is an optional dependency declared in `pyproject.toml` under `[project.optional-dependencies]` as `mcp = ["mcp"]`, installable via `pip install xclif[mcp]`.

Changes to existing files:
- `src/xclif/__init__.py` (`Cli`): add `serve_mcp()` method; conditionally inject `mcp` subcommand in `__post_init__` only when `import mcp` succeeds
- `src/xclif/command.py`: add `"mcp"` to `_AGENT_HIDDEN_SUBCOMMANDS`

---

## `mcp.py` internals

### `_command_to_json_schema(cmd: Command) -> dict`

Builds the JSON Schema object for a leaf command's MCP tool inputs.

Type mapping from `converter`:
- `str` → `{"type": "string"}`
- `int` → `{"type": "integer"}`
- `float` → `{"type": "number"}`
- `bool` → `{"type": "boolean"}`
- Literal converter (has `__choices__`) → `{"type": "string", "enum": [...]}`

For `Argument`:
- Fixed positionals → required properties using the type mapping above
- Variadic positional → `{"type": "array", "items": <type>}`
- `list[T]` options → `{"type": "array", "items": <type>}`

The `required` list contains only the positional argument names (not options, which all have defaults or are optional).

### `_collect_leaf_commands(cmd: Command, prefix: str) -> list[tuple[str, Command]]`

Recursively walks the command tree. Returns a flat list of `(tool_name, command)` pairs where `tool_name` is the full path joined by `_` (e.g. `"config_get"`). Skips entries in `_AGENT_HIDDEN_SUBCOMMANDS` and alias entries (same object under multiple keys, detected by `id()`).

### `make_mcp_command(root: Command) -> Command`

Builds the injected `mcp` subcommand. Its `run()` function calls `serve_mcp_stdio(root)` and returns 0. No arguments or options (stdio only).

### `serve_mcp_stdio(root: Command)`

Entry point for the MCP server. Hard-imports `mcp` (callers only reach this if the package was found at startup, but `serve_mcp()` on `Cli` guards with a clear error just in case):

```python
try:
    import mcp.server.stdio
    from mcp.server import Server
    from mcp.types import Tool, TextContent
except ImportError:
    raise SystemExit(
        "The 'mcp' package is required for MCP server support.\n"
        "Install it with: pip install xclif[mcp]"
    )
```

Steps:
1. Call `_collect_leaf_commands(root, "")` to get all leaf tools.
2. Create an `mcp.server.Server` instance named after `root.name`.
3. Register a `list_tools` handler returning `[Tool(name=tool_name, description=cmd.short_description, inputSchema=_command_to_json_schema(cmd)) for tool_name, cmd in leaf_commands]`.
4. Register a `call_tool` handler that looks up the tool by name, calls `_mcp_input_to_argv(cmd, arguments)` to build an argv list, redirects stdout to a `StringIO` buffer via `contextlib.redirect_stdout`, calls `cmd.execute(argv)`, then returns `[TextContent(type="text", text=buffer.getvalue())]`.
5. Run `mcp.server.stdio.stdio_server(server)` (blocks).

### `_mcp_input_to_argv(cmd: Command, inputs: dict) -> list[str]`

Converts an MCP tool input dict back to an argv list for `cmd.execute()`:

1. Positional arguments: append values in declaration order (convert to `str`).
2. Options: for each key in `cmd.options`:
   - `bool`: if truthy, emit `--name`
   - `list[T]`: emit `--name val` for each element
   - other: emit `--name value`

Values not present in `inputs` are omitted (the parser uses defaults).

---

## Tool naming

Tool name = full command path joined by `_`. Examples:
- Root-level `greet` → `"greet"`
- `config get` → `"config_get"`
- `config set` → `"config_set"`

---

## Error handling

- Missing `mcp` package: subcommand silently absent at startup; `SystemExit` with `pip install xclif[mcp]` instructions if `serve_mcp()` is called directly without the package.
- `UsageError` from `command.execute()`: already caught internally; stderr output is captured and returned as a tool error `TextContent`.
- Unknown tool name in `call_tool`: raise `mcp.McpError` with a clear message.

---

## `Cli` changes

### `__post_init__` addition

Only inject if the `mcp` package is available:

```python
try:
    import mcp as _mcp_pkg  # noqa: F401
    from xclif.mcp import make_mcp_command
    self.root_command._assert_no_arguments(adding="mcp")
    self.root_command.subcommands["mcp"] = make_mcp_command(self.root_command)
except ImportError:
    pass  # mcp optional dep not installed; subcommand silently absent
```

### `serve_mcp()` method

```python
def serve_mcp(self) -> None:
    """Start an MCP stdio server exposing all leaf commands as tools."""
    self._finalize()
    from xclif.mcp import serve_mcp_stdio
    serve_mcp_stdio(self.root_command)
```

---

## Testing

`tests/test_mcp.py`:

1. **Schema generation** — `_command_to_json_schema`:
   - Command with a `str` positional arg → required string property
   - Command with `int` arg + `bool` option → correct types, only arg in `required`
   - Variadic `str` arg → `array` property
   - `list[str]` option → `array` property
   - Literal arg → `enum` property

2. **Tree walking** — `_collect_leaf_commands`:
   - Flat tree → correct tool names
   - Nested tree → `_`-joined names
   - Hidden subcommands (`completions`, `mcp`) excluded
   - Alias entries (same `Command` object under two keys) not duplicated

3. **Argv reconstruction** — `_mcp_input_to_argv`:
   - Positional args in order
   - Bool option: `True` → `["--flag"]`, `False` → omitted
   - List option → repeated `--name val` pairs
   - Missing optional → omitted

4. **Integration** — mock `mcp` package import; build a small command tree; call the tool handler dict → `execute()` → check stdout via `capsys`.

5. **Soft dependency error** — patch `builtins.__import__` to raise `ImportError` for `mcp`; assert `serve_mcp_stdio` raises `SystemExit` with `xclif[mcp]` install instructions.

6. **`mcp` subcommand injection** — when `mcp` package is present, `Cli.__post_init__` injects `mcp` into subcommands; `mcp` is in `_AGENT_HIDDEN_SUBCOMMANDS` so absent from agent help. When package is absent, subcommand is silently not injected.

---

## Acceptance criteria (from issue)

- [x] `Cli.serve_mcp()` starts an MCP stdio server exposing all leaf commands as tools
- [x] `myapp mcp` subcommand is auto-injected and invokes `serve_mcp()`
- [x] Tool input schemas correctly reflect positional args (required) and options (optional with defaults)
- [x] `mcp` is hidden from agent help output
- [x] Clear error if `mcp` package is not installed
- [x] Tests covering schema generation and tool dispatch
