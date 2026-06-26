# Changelog

## Unreleased

## 0.6.1 — Shared soft-wrap console (2026-06-25)

### Added
- A shared `console` is now exported from `xclif`: a `rich.console.Console` configured with `soft_wrap=True`. Use `console.print(...)` for command output instead of `rich.print(...)` so long strings (e.g. file paths) are emitted as single logical lines and wrapped by the terminal rather than hard-broken mid-line by Rich. The console is built lazily on first access, so `import xclif` does not import Rich on the hot path.

## 0.6.0 — Logging! (2026-06-14)

### Added
- Logging mini-library: `get_logger()`, `configure_logging()`, `RichLogHandler`, and `level_from_verbosity()` provide standard `logging` integration with Rich stderr output wired to Xclif verbosity and color options. A ready-to-use `log` logger and `f` formatting namespace are bundled and exported from `xclif`. (#50)
- Parser support for clustered repeated boolean short flags, including `-vv` and `-vvv` for verbosity.
- `Cli(logging=False)` (also on `from_routes` and `from_manifest`): leave logging entirely to your application. Xclif no longer touches the root logger on dispatch, but the verbosity count remains available via `get_context().verbosity`.
- `Cli(completions_command=False)`: suppress the auto-injected `completions` subcommand, parallel to the existing `config_command` and `mcp_command` flags.
- Unprefixed environment-variable fallback for `WithConfig` parameters: `API_KEY` is consulted when `MYAPP_API_KEY` is unset. Priority is unchanged — CLI > prefixed env > unprefixed env > config > default.
- `xclif.Path` is now a first-class parameter type. It is registered as a converter and exported in `__all__`, so `script: Path` is a usable, documented contract.

### Changed
- AI-agent detection no longer keys off "stdout is not a TTY". Xclif now detects 14 specific AI coding agents (Claude Code, Cursor, Gemini CLI, and others) via environment variables. Piping `--help` to `grep` no longer triggers the agent-optimized format, while real agents still get it.

### Fixed
- `Optional[X]` / `X | None` options no longer crash at decorator time. The single non-None Union member is unwrapped and its converter applied, so an option with a `None` default works. (#68)
- `xclif.Path` parameters no longer crash with "Unsupported type" — `Path` was documented but missing from the converter table. (#70)
- Auto-injected `completions` and `mcp` subcommands no longer silently overwrite a user-defined subcommand of the same name, and are skipped (rather than raising) when the root command declares positional arguments — making a single root command with a positional expressible. (#61, #73)

## 0.5.1 — Configurations for MCP (2026-05-05)

### Added
- `show_no_description` option on `@command()` decorator and `Cli` class: suppress "No description" placeholder per-command or globally
- `Cli(mcp_command=False)` option to suppress auto-injected `mcp` subcommand even when `mcp` package is installed
- Documentation for `Cascade` annotation (user-defined cascading options) and MCP server mode

## 0.5.0 — Cascade, MCP server mode, and error UX polish (2026-05-05)

### Added
- `Cascade` annotation: mark options with `Cascade()` to propagate their values to subcommands, accessible via `get_context()["option_name"]`. Designed for configurable multi-level CLIs — declare on the root command and read in any subcommand.
- MCP server mode: auto-expose CLI commands as MCP tools. Calling `xclif.mcp.serve(app)` serves your CLI as Model Context Protocol tools for AI agents. (#56)
- `show_no_description` option on `@command()`: set to `False` to suppress the default "No description provided" placeholder. (#62)
- Config `path` command now prints the config file path (not just its parent directory). New `--dir` flag returns the config directory instead.
- Validation of `--colors` option values: invalid values now raise a clear error instead of being silently accepted. (#52)
- Detection of implicit option collisions: user-defined options that shadow framework-owned implicit options (`--help`, `--verbose`, `--colors`) are now caught with an actionable error at command construction. (#58)
- Private route modules (names starting with `_`) are now filtered out during route discovery. (#53)
- Error messages now include `"For more information, try --help"` on usage errors, using the command name with bold cyan formatting for the copy-pasteable hint.

## 0.4.3 — Fixed positional args crash (2026-04-10)

### Fixed
- Parser crash when variadic args appear after options in function signature. Options are now interleaved with fixed positional args in signature order before appending variadic items, preventing positional/keyword argument conflicts.

## 0.4.2 — Terminal soft wrap behavior changes (2026-04-10)

## 0.4.1 — Minor adjustments in help text system (2026-04-08)

### Added
- `--help=plain`, `--help=rich`, and `--help=agent` modes: explicitly override help format auto-detection. Bare `--help` still auto-detects based on TTY. `plain` gives the same layout as `rich` but with no ANSI/color; `agent` gives the compact token-efficient format.
- `optional_value` field on `_DefinitionOption`: options can now be used as bare flags with a default value, or with `=value` syntax.

### Changed
- Help section headers (`Usage:`, `Subcommands:`, `Arguments:`, `Options:`) are now bold white instead of bold cyan. Only subcommand/option names remain cyan.

## 0.4.0 — Agent help text and Options Cascade (2026-04-08)

### Added
- `get_context()` API: access cascading framework state (`Context` class) from within command handlers. Exported from `xclif`. (#51)
- Agent-optimized help: `print_agent_help()` emits token-efficient plain-text help for LLM consumers; auto-detected when stdout is not a TTY. Positional arguments are now shown in agent help output.
- Colorized help output: cyan accents and dimmed descriptions in `--help` via Rich.

### Changed
- Renamed internal `definition.Option` to `_DefinitionOption` to avoid confusion with the public `Option` annotation marker.
- Refactored `_set_context` into separate `set`/`reset` methods for type safety.

### Fixed
- Benchmarks now set `FORCE_COLOR=1` so `--help` benchmarks measure Rich output correctly.

## 0.3.0 — Aliases! (2026-04-08)

### Added
- Subcommand aliases: `@command("name", "alias1", "alias2")` lets commands declare alternative names. Aliases are registered in the parent's subcommands dict, included in shell completions, and shown in the command's own Usage line. (#47)
- Markdown docstrings: command descriptions are now rendered as Markdown in `--help` output via Rich, supporting **bold**, `code`, lists, blockquotes, and more.
- `local_config` parameter on `Cli`, `from_routes`, and `from_manifest`: set a filename (e.g. `".myapp.toml"`) to load a per-project config from the current working directory. Local values are deep-merged over user-level config. Supports `.toml` and `.json`. Disabled by default.
- `__version__` is now exported (`from xclif import __version__`).

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
