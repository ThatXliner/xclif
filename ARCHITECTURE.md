# Xclif — Internal Architecture

This document describes how Xclif works internally. It is aimed at contributors
who want to fix bugs, add features, or understand the codebase.

## Module Dependency Graph

```
__init__.py  (Cli, public API)
    ├── command.py   (Command, @command, extract_parameters)
    │   ├── annotations.py  (type → converter registry)
    │   ├── definition.py   (Argument, Option, IMPLICIT_OPTIONS)
    │   ├── constants.py    (NO_DESC, padding values)
    │   └── parser.py       (parse_and_execute_impl, _parse_token_stream)
    │       └── definition.py
    └── importer.py  (route discovery via pkgutil)
```

There are no circular imports. `parser.py` uses `TYPE_CHECKING` to reference
`Command` without importing it at runtime.

## Data Flow

A CLI invocation goes through four phases:

### 1. Route Discovery (`Cli.from_routes`)

```
routes/ package  →  importer.get_modules()  →  inspect.getmembers()  →  Command tree
```

`get_modules` uses `pkgutil.walk_packages` to recursively find every module
under the routes package. Each module is expected to export exactly one
`Command` (created via `@command()`). The dotted module path determines
placement in the command tree:

```
routes/__init__.py        →  root command
routes/greet.py           →  root.subcommands["greet"]
routes/config/__init__.py →  root.subcommands["config"]  (namespace)
routes/config/set.py      →  root.subcommands["config"].subcommands["set"]
```

Intermediate namespace commands (like `config`) are auto-created with a default
action that prints short help.

### 2. Command Construction (`@command` decorator)

The `@command()` decorator calls `extract_parameters(func)` which introspects
the function signature via `inspect.signature`:

| Signature pattern          | Result                              |
|----------------------------|-------------------------------------|
| `name: str`                | Positional `Argument`               |
| `greeting: str = "hi"`    | Named `Option` with default         |
| `*files: str`              | Variadic `Argument` (must be last)  |
| `dry_run: bool = False`   | Boolean flag `Option`               |

Type annotations are resolved to converter callables through
`annotations.py`'s registry (`str`, `int`, `float`, `bool`).

Auto-generated short aliases (e.g. `-n` for `--name`) are assigned during
extraction, skipping any letters already claimed by implicit options (`-h`, `-v`).
Explicit aliases may be provided with `Option(aliases=[...])`; these can be short
or long forms and skip auto-generation.

### 3. Token Parsing (`_parse_token_stream`)

When `command.execute(args)` is called, it delegates to `parse_and_execute_impl`,
which calls `_parse_token_stream` to do the actual token scanning.

The scanner is a single left-to-right pass over the token list. It recognises:

- **Long options**: `--name value`, `--name=value`
- **Short options**: `-n value`, `-v` (aliases resolved via `_build_alias_map`)
- **Long aliases**: `--alias value`, `--alias=value`
- **Boolean flags**: `--verbose`, `-v` (no value consumed)
- **`--` separator**: everything after it becomes a raw positional
- **Subcommand names**: scanning stops immediately; the index is returned
- **Positionals**: anything else is collected in order

Options and positionals can be **interspersed** — `Alice --template "Hi, {}!"`
and `--template "Hi, {}!" Alice` both work. The **greedy consumption rule**
means `--format json` always eats `json` as the option value, even if `json`
is also a subcommand name.

The scanner returns a triple:
```python
(positionals: list[str], parsed_opts: dict[str, list], subcmd_index: int | None)
```

### 4. Dispatch and Execution (`parse_and_execute_impl`)

After scanning, `parse_and_execute_impl` handles the result in order:

1. **Implicit options**: `--help` prints help and returns 0. `--version`
   (root-only) prints the version and returns 0.
2. **Cascading context**: Cascading implicit options (like `--verbose`) are
   accumulated into a `context` dict that is passed down to child commands.
   This context is *not* forwarded as kwargs to `run()`.
3. **Subcommand dispatch**: If a subcommand was detected, recursively call
   `parse_and_execute_impl` with the remaining args and updated context.
4. **Namespace default**: If the command has subcommands but received no
   positionals and no user options, print short help (the "did you mean?"
   experience).
5. **Leaf execution**: Convert positionals to typed arguments, resolve option
   defaults, and call `command.run(*args, **kwargs)`. A `None` return is
   coerced to `0`.

## Key Abstractions

### `Command` (command.py)

The central node type. Every command — root, namespace, or leaf — is a
`Command`. Key fields:

| Field              | Purpose                                          |
|--------------------|--------------------------------------------------|
| `name`             | Display name (used in help text, version output)  |
| `run`              | The callable to invoke                            |
| `arguments`        | Ordered list of positional `Argument`s            |
| `options`          | User-defined `Option`s (forwarded to `run()`)     |
| `subcommands`      | Child commands (mutually exclusive with variadic args) |
| `implicit_options` | Framework options like `--help`, `--verbose`       |
| `version`          | Set only on root command by `Cli`                 |

### `Argument` / `Option` (definition.py)

Simple dataclasses. `Argument` has a `variadic` flag. `Option` has `aliases`
(short or long forms), `cascading` (propagates to children), and `default`.

### Implicit vs User Options

This is the most important architectural boundary. Every `Command` has two
option namespaces:

- **`implicit_options`**: Framework-owned. `--help`, `--verbose`, `--colors`.
  Handled by the parser *before* dispatch. Never passed to `run()`.
- **`options`**: User-defined. Declared in the function signature. Passed as
  kwargs to `run()`.

`--version` is a special case: it is injected into `implicit_options` by `Cli`
on the root command only. Subcommands don't recognise it.

### `Cli` (__init__.py)

The top-level entry point. Responsibilities:

- Owns the root `Command` and the version string
- Auto-detects version from package metadata (fallback: explicit `version=` kwarg)
- Injects the `completions` subcommand
- Injects `--version` into root's implicit options
- `cli()` calls `sys.exit(root.execute())`

### `IMPLICIT_OPTIONS` (definition.py)

A module-level dict that serves as the default implicit options for every new
`Command`. The `Command.__post_init__` copies these if none are provided.
This ensures a fresh dict per command (avoiding shared mutable state) while
keeping a single source of truth for the defaults.

## How to Add a New Feature

### New option type (e.g. `Path`)

1. Add the converter to `_default_converters` in `annotations.py`
2. Add the type to the `ScalarParameterTypes` union
3. Write tests in `test_command.py` for `extract_parameters`

### New implicit option (e.g. `--quiet`)

1. Add it to `IMPLICIT_OPTIONS` in `definition.py`
2. Handle it in `parse_and_execute_impl` in `parser.py` (after the help/version block)
3. If cascading, add context accumulation logic
4. Reserve its aliases (e.g. `-q`) in the `IMPLICIT_OPTIONS` entry

### New CLI-level feature (e.g. `--no-color`)

Follow the `--version` pattern:
1. Add the option in `Cli.__post_init__` → inject into `root_command.implicit_options`
2. Handle it in `parse_and_execute_impl`

## Testing Strategy

Tests live in `tests/` and are run with `uv run pytest`.

| File                          | Scope                                        |
|-------------------------------|----------------------------------------------|
| `test_parser.py`              | `_parse_token_stream` + `parse_and_execute_impl` unit tests |
| `test_command.py`             | `extract_parameters`, `Command`, `Argument`/`Option` |
| `test_cli.py`                 | `Cli` construction, routing, `from_routes`    |
| `test_integration_greeter.py` | Full-stack tests against the greeter experiment |

The greeter experiment (`experiments/greeter/`) serves as both an example app
and an integration test fixture. `conftest.py` adds it to `sys.path` so the
test suite can import it directly.

### Conventions

- Unit tests should construct `Command` objects directly — don't go through `Cli` unless testing `Cli` itself.
- Integration tests use `root.execute([...])` with explicit arg lists (never `sys.argv`).
- Use `capsys` for output assertions rather than mocking `print`.
