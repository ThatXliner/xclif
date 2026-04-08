# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Xclif ("Xliner's CLI Framework") is a Python CLI framework where directory structure defines the command tree. Type hints on function signatures define the CLI contract (positional args, options, flags). Built-in Rich integration for help pages and errors.

## Commands

```bash
# Run all tests
uv run pytest

# Run a single test file or test
uv run pytest tests/test_parser.py
uv run pytest tests/test_parser.py::test_name

# Run tests with coverage
uv run pytest --cov=src/xclif --cov-report=term-missing

# Build docs
uv run sphinx-build docs docs/_build/html

# Build distribution
uv build

# Use `just` as a task runner (see Justfile)
just test
just cov
just docs
```

There is no separate lint/format command configured. The project uses black, isort, ruff, and mypy (see badges in README) but these are not wired into a `just` target.

## Architecture

Source lives in `src/xclif/`. The key execution flow is:

1. **Route discovery** (`importer.py`) — `pkgutil.walk_packages` finds modules under a routes package; each module exports one `Command`
2. **Command construction** (`command.py` + `annotations.py` + `definition.py`) — `@command()` decorator introspects function signatures via `inspect.signature` to build `Argument`/`Option` lists
3. **Token parsing** (`parser.py`) — single left-to-right pass scanner; handles long/short options, `--` separator, interspersed positionals, subcommand detection
4. **Dispatch** (`parser.py: parse_and_execute_impl`) — handles implicit options (help/version/verbose), cascading context, subcommand recursion, then leaf execution

Key architectural boundary: **implicit options** (framework-owned: `--help`, `--verbose`, `--colors`) vs **user options** (from function signature). Implicit options are handled before dispatch and never passed to `run()`.

Other modules:
- `compiler.py` — pre-builds a static manifest to skip route-walking at startup
- `completions.py` — shell completion generation (bash/zsh/fish)
- `config.py` + `config_commands.py` — `WithConfig[T]` for config file/env var resolution
- `validation.py` — parameter validation
- `errors.py` — custom exception types

## Testing

- Unit tests construct `Command` objects directly; only `test_cli.py` goes through `Cli`
- Integration tests use `root.execute([...])` with explicit arg lists (not `sys.argv`)
- Use `capsys` for output assertions, not mocking `print`
- The greeter experiment (`experiments/greeter/`) is both an example and integration test fixture; `conftest.py` adds it to `sys.path`

## Python

- Requires Python >= 3.12
- Always use `uv run` to execute scripts/tests (ensures correct virtualenv)
- Build system: hatchling
