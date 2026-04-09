# Agent-Optimized Help Output

## Problem

When an agent (like Claude Code) calls `mycli --help`, it receives Rich-formatted output with ANSI escape codes, decorative formatting, and framework-owned options that waste tokens and provide no value to an LLM consumer. A hyper-short, token-efficient format reduces cost and improves agent comprehension.

## Decision: Format D (hyper-short)

Token experiment results on the greeter example:

| Format | Tokens | Chars |
|--------|--------|-------|
| Plain text (current sans Rich) | 106 | 456 |
| JSON | 285 | 1139 |
| Paragraph | 82 | 304 |
| **Hyper-short** | **52** | **208** |
| Markdown | 106 | 357 |

Hyper-short wins at ~50% of plain text and ~18% of JSON.

## Agent Help Format

Example output for the greeter CLI:

```
greeter: An over-engineered hello world CLI.

greet - Greet someone by name. Options: --name STR, --template STR (default: "Hello, {}!")
config get - Print the current config.
config set - Set config values.
```

Rules:

- **Line 1**: `{name}: {short_description}`
- **Command lines**: One per leaf command, flattened path. Format: `{path} - {short_description}. Options: {opts}` (options omitted if none)
- **Options format**: `--{name} {TYPE}` with `(default: {val})` if non-empty/non-None. Booleans show as flags with no TYPE.
- **Filtered out**: All implicit options (`--help`, `--verbose`, `--colors`, `--version`) and framework subcommands (`completions`).
- **Recursion**: Walk the full command tree. Flatten all leaf commands regardless of depth.
- **Non-leaf groups** (like `config`) are skipped — only their children appear.

## TTY Detection & Dispatch

Use `rich.console.Console().is_terminal` for detection. It already handles `isatty()`, `FORCE_COLOR`, `TTY_COMPATIBLE`, Jupyter, and IDLE.

Both `print_short_help()` and `print_long_help()` get an early guard:

```python
if not _get_console().is_terminal:
    self.print_agent_help()
    return
```

No new CLI flags. Pure auto-detection.

Framework subcommands to hide are tracked in a set: `_AGENT_HIDDEN_SUBCOMMANDS = {"completions"}`.

## Implementation: Approach 1 (dual-method)

Add `print_agent_help()` to `Command`. The existing `print_short_help()` and `print_long_help()` check `is_terminal` and delegate when non-TTY.

## Benchmark Updates

`bench_frameworks.sh` and `bench_frameworks.py` run `--help` via subprocess (piped, non-TTY). To keep the comparison fair against Click/Typer (which always emit formatted help):

- `bench_frameworks.sh`: Set `FORCE_COLOR=1` in the environment for xclif invocations.
- `bench_frameworks.py`: Pass `env={**os.environ, "FORCE_COLOR": "1"}` to subprocess calls.

## Test Updates

Existing help tests are smoke tests (no crash, exit code 0). They'll naturally hit the agent format path in pytest (non-TTY). Add new tests for agent format content: flattened output, filtering of implicit options/framework subcommands, recursive tree walking.

## Files to Modify

- `src/xclif/command.py` — add `print_agent_help()`, TTY guard in `print_short_help()`/`print_long_help()`
- `benchmarks/bench_frameworks.sh` — `FORCE_COLOR=1`
- `benchmarks/bench_frameworks.py` — env override in subprocess calls
- `tests/test_command.py` — new agent help tests
