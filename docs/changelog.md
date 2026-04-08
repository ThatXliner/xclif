# Changelog

## Unreleased

### Added
- Markdown docstrings: command descriptions are now rendered as Markdown in `--help` output via Rich, supporting **bold**, `code`, lists, blockquotes, and more.
- `local_config` parameter on `Cli`, `from_routes`, and `from_manifest`: set a filename (e.g. `".myapp.toml"`) to load a per-project config from the current working directory. Local values are deep-merged over user-level config. Supports `.toml` and `.json`. Disabled by default.

## 0.2.0 — Developer Experience (2026-04-04)

### Added
- `Arg` annotation marker: attach `description` and display `name` to positional arguments via `Annotated[str, Arg(description="...", name="FILE")]`.
- `Option` annotation marker: attach `description` and override CLI flag `name` via `Annotated[bool, Option(description="...", name="dry-run")]`.
- `Literal["a", "b", ...]` type support: constrain an argument or option to a fixed set of string values. Invalid input raises a `UsageError`; help output shows `[a|b|...]` inline.
- Shell completions: `completions <shell>` — single command with a positional `shell` argument (`bash`, `zsh`, or `fish`), replacing the old per-shell subcommands. When stdout is a TTY, prints a colored install hint to stderr with the shell-specific destination path.
- `WithConfig[T]` — parameters annotated with `WithConfig[T]` fall back to environment variables and config files (TOML/JSON) when not supplied on the CLI. Priority: CLI > env > config > default. (#23, #24)
  - `WithConfig[str]` is sugar for `Annotated[str, WithConfig()]`
  - `env_prefix` and `config_name` configurable on `Cli`, `from_routes`, and `from_manifest`
  - Config files auto-detected via `platformdirs` (TOML preferred, JSON fallback)
  - Dotted key paths for nested config values
  - Auto-injected `config get/set/path` subcommands (skipped if app already has `config`)
  - Type conflict detection at init and compile time with actionable error messages
  - New dependencies: `platformdirs`, `tomlkit`

### Changed
- `WithConfig` is now a zero-argument marker. The `env` and `key` override fields have been removed. Env var names are always `<PREFIX>_<PARAM_UPPERCASED>`; config keys are always the parameter name.
- **Breaking:** `completions bash/zsh/fish` subcommands replaced by `completions <shell>` positional argument.

## 0.1.0 — Usable Core

Initial release.
