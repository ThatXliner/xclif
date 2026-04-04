# Arg/Option Annotation Markers + WithConfig Simplification

**Date:** 2026-04-04

## Summary

Two related changes:

1. Add `Arg` and `Option` as `Annotated` metadata markers so users can attach descriptions and name overrides to parameters without leaving the function signature.
2. Simplify `WithConfig` to a no-argument marker — drop `env` and `key` override fields.

## Motivation

Currently all parameters get `NO_DESC` ("No description") in help output because there is no way to attach a description to a function parameter without leaving the signature. The docstring describes the command, not individual params.

`WithConfig` overrides (`env=`, `key=`) were added as an escape hatch but actively cause complexity (the last 3 commits before this were all conflict-detection fixes). xclif is opinionated — if the auto-derived env var or config key name doesn't fit, users should rename their parameter or not use `WithConfig`.

## User-Facing API

### `Arg`

```python
from xclif import Arg, command
from typing import Annotated

@command()
def copy(
    src: Annotated[str, Arg(description="Source file", name="SRC")],
    dst: Annotated[str, Arg(description="Destination path", name="DST")],
) -> None:
    """Copy SRC to DST."""
```

- `description`: shown in help output next to the argument
- `name`: display name in help (e.g. `SRC` instead of `src`); does not affect parsing

### `Option`

```python
from xclif import Option, command
from typing import Annotated

@command()
def build(
    dry_run: Annotated[bool, Option(description="Don't actually run", name="dry-run")] = False,
) -> None:
    """Build the project."""
```

- `description`: shown in help output next to the flag
- `name`: overrides the CLI flag name (`--dry-run` instead of `--dry-run` auto-derived). The kwarg passed to `run()` is always the Python parameter name (`dry_run`).

### Composing with `WithConfig`

`Arg`/`Option` and `WithConfig` can coexist in the same `Annotated`:

```python
name: Annotated[str, Arg(description="Person to greet"), WithConfig()]
greeting: Annotated[str, Option(description="Greeting template"), WithConfig()] = "Hello, {}!"
```

### `WithConfig` simplified

```python
@dataclass(frozen=True)
class WithConfig:
    """Marker for parameters that can be read from a config file or env var."""

    def __class_getitem__(cls, item: type) -> type:
        from typing import Annotated
        return Annotated[item, cls()]
```

No `env` or `key` fields. Env var and config key are always auto-derived from the parameter name and env prefix.

## New Classes

Both live in `src/xclif/__init__.py` and are exported from `__all__`:

```python
@dataclass(frozen=True)
class Arg:
    description: str | None = None
    name: str | None = None      # display name in help (e.g. "FILE")

@dataclass(frozen=True)
class Option:
    description: str | None = None
    name: str | None = None      # CLI flag name override (e.g. "dry-run")
```

## Changes to `extract_parameters`

`annotations.py` gets a new `unwrap_param_metadata` function that scans `Annotated` metadata for `Arg`/`Option` instances alongside the existing `unwrap_with_config`. `extract_parameters` then:

1. Calls `unwrap_param_metadata` to extract `Arg`/`Option` metadata and `WithConfig`
2. Determines arg-vs-option by presence of default (existing logic)
3. Validates: `Arg` metadata on an option → error; `Option` metadata on an arg → error
4. Uses `description` from metadata if present, else `NO_DESC`
5. For options: uses `name` override for `Option.name` (the CLI flag); dict key stays as Python param name
6. For args: uses `name` override for display in help only

## Changes to `WithConfig`

- Remove `env: str | None` and `key: str | None` fields
- Remove override resolution logic from `parser.py` (`_resolve_with_config`)
- Remove override conflict detection from `validation.py`
- Update compiler output to no longer emit `env=`/`key=` kwargs

## Mismatch Errors

```
Arg() used on option parameter 'greeting' — use Option() instead
Option() used on argument parameter 'src' — use Arg() instead
```

## Help Output (illustrative)

```
Usage: myapp copy SRC DST

Copy SRC to DST.

Arguments:
  SRC    Source file
  DST    Destination path
```

```
Usage: myapp build [OPTIONS]

Build the project.

Options:
  --dry-run    Don't actually run
  -h, --help   Show this help message and exit
```

## Docs to Update

- `docs/options.rst` — add section on `Arg`/`Option` markers
- `docs/config.rst` — remove `WithConfig(env=..., key=...)` override examples
- `docs/api.rst` — add `Arg`, `Option` to API reference
- `docs/superpowers/specs/2026-04-04-with-config-design.md` — note that override fields were dropped
- `docs/changelog.md` — add entries for both changes

## Files to Change

| File | Change |
|------|--------|
| `src/xclif/__init__.py` | Add `Arg`, `Option` classes; simplify `WithConfig` |
| `src/xclif/annotations.py` | Add `unwrap_param_metadata` |
| `src/xclif/command.py` | Update `extract_parameters` to use metadata |
| `src/xclif/parser.py` | Remove `env`/`key` override resolution |
| `src/xclif/validation.py` | Remove override conflict detection |
| `src/xclif/compiler.py` | Remove `env=`/`key=` from generated output |
| `docs/options.rst` | Document `Arg`/`Option` markers |
| `docs/config.rst` | Remove override examples |
| `docs/api.rst` | Add `Arg`, `Option` |
| `docs/changelog.md` | Add entries |
