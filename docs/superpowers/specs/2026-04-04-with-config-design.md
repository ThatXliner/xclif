# WithConfig[T]: Config File and Env Var Resolution

**Issues:** #23, #24
**Milestone:** 0.2.0 — Developer Experience

## Summary

`WithConfig[T]` allows CLI parameters (arguments and options) to fall back to environment variables and config files when not supplied on the command line. Priority order: **CLI flag > env var > config file > default**.

## User-Facing API

### Simple case

`WithConfig[str]` is sugar for `Annotated[str, WithConfig()]` — uses global env prefix and param name as config key:

```python
from xclif import WithConfig, command

@command()
def _(name: WithConfig[str], template: WithConfig[str] = "Hello, {}!") -> None:
    """Greet someone."""
    print(template.format(name))
```

### Override case

Custom env var or config key via `Annotated`:

```python
from typing import Annotated
from xclif import WithConfig, command

@command()
def _(name: Annotated[str, WithConfig(env="MY_NAME", key="user_name")]) -> None:
    ...
```

### Cli setup

```python
cli = Cli.from_routes(routes, env_prefix="GREET", config_name="greeter")
```

- `env_prefix` defaults to uppercased root command name
- `config_name` defaults to root command name
- Config path: `platformdirs.user_config_dir(config_name) / "config.toml"` (or `.json`)

## WithConfig Class

```python
@dataclass(frozen=True)
class WithConfig:
    env: str | None = None    # full env var name override
    key: str | None = None    # config file key override (supports dotted paths)

    def __class_getitem__(cls, item: type) -> type:
        from typing import Annotated
        return Annotated[item, cls()]
```

- `WithConfig[str]` produces `Annotated[str, WithConfig(env=None, key=None)]`
- `Annotated[str, WithConfig(env="MY_NAME")]` allows per-param overrides
- One concept, two levels of verbosity

## Storage on Definitions

New `config` field on `Option` and `Argument`:

```python
@dataclass
class Option[T]:
    ...
    config: WithConfig | None = None  # None means not config-backed

@dataclass
class Argument[T]:
    ...
    config: WithConfig | None = None
```

`extract_parameters` detects `WithConfig` in `Annotated` metadata and populates this field.

## Config Resolution (in the parser)

Resolution happens in `parse_and_execute_impl`, after token parsing, before calling `command.run()`:

```
For each option/argument with config metadata:
    if value was provided on CLI -> use it
    else if env var is set -> convert and use it
    else if config file has the key -> convert and use it
    else -> fall back to default (existing behavior)
```

### Env var resolution

For param `template` with prefix `GREETER`:
- Default: `GREETER_TEMPLATE` (prefix + `_` + uppercased param name)
- Override: `WithConfig(env="CUSTOM_VAR")` uses that exact name

### Config key resolution

For param `template`:
- Default: `template` (the param name)
- Override: `WithConfig(key="my_template")` uses that exact key

### Dotted key paths

`WithConfig(key="greeter.name")` resolves to `config["greeter"]["name"]` in both TOML and JSON:

**TOML:**
```toml
[greeter]
name = "Alice"
```

**JSON:**
```json
{
  "greeter": {
    "name": "Alice"
  }
}
```

### Config context

- `Cli.__post_init__` loads the config file once and stores it in a context dict along with `env_prefix`
- `parse_and_execute_impl` receives context and uses it during resolution
- Config file is read once at startup, not per-command

### Config file location and auto-detection

- Path: `platformdirs.user_config_dir(config_name)` / `config.toml` checked first, then `config.json`
- Missing file is fine — no config values

## Auto-Injected Config Subcommands

When at least one `WithConfig` param exists in the command tree, xclif auto-injects a `config` subcommand group (similar to how `completions` is auto-injected):

- `config get [key]` — print all config values or a specific one
- `config set <key> <value>` — write to the config file (creates as TOML if none exists)
- `config path` — print the config file location

If the app already defines a `config` subcommand, auto-injection is skipped (no error, defers to the developer's version).

Writing uses `tomlkit` to preserve comments and formatting on round-trip. If no config file exists, `config set` creates a TOML file. If a JSON file exists, it writes JSON.

## Conflict Detection

Checked at `Cli.__post_init__` and during `xclif compile`, before any command runs.

### What's checked

Walk all commands in the tree, collect every `Option`/`Argument` with `config` set. For each resolved config key and env var, verify all parameters sharing that key have the same converter type.

- Same key + same type = shared intentionally (allowed)
- Same key + different type = conflict (error)

### Error messages

Actionable, developer-facing, with a suggested fix:

```
WithConfig conflict: config key 'name' is used as str (in 'greet') and int (in 'farewell').

To fix, give one a distinct key:
    name: Annotated[str, WithConfig(key="greet_name")]
```

```
WithConfig conflict: env var 'GREETER_NAME' maps to str (in 'greet') and int (in 'farewell').

To fix, give one a distinct env var:
    name: Annotated[str, WithConfig(env="GREETER_GREET_NAME")]
```

## Compiler Integration

- `extract_parameters` detects `WithConfig` in annotations and populates the `config` field — already runs at compile time
- Compiler output emits `config=WithConfig(env=..., key=...)` in generated `Option(...)`/`Argument(...)` calls
- Conflict check runs during compilation, raises an error that stops the build

## Dependencies

- **`platformdirs`** — OS-specific config directory resolution
- **`tomlkit`** — TOML reading and writing (replaces stdlib `tomllib`; preserves comments on round-trip)

## Changes to Greeter Example

- `greet.py` simplifies to `WithConfig[str]` annotations instead of manual `_load_config()`
- `config/read.py` and `config/set.py` remain as-is (app-level commands)
