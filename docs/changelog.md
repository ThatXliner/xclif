# Changelog

## 0.2.0 — Developer Experience (unreleased)

### `WithConfig[T]` — config file and env var resolution (#23, #24)

Parameters annotated with `WithConfig[T]` now fall back to environment variables and
config files (TOML/JSON) when not supplied on the CLI. Priority: CLI > env > config > default.

- `WithConfig[str]` is sugar for `Annotated[str, WithConfig()]`
- Per-parameter overrides via `Annotated[str, WithConfig(env="CUSTOM", key="section.param")]`
- `env_prefix` and `config_name` configurable on `Cli`, `from_routes`, and `from_manifest`
- Config files auto-detected via `platformdirs` (TOML preferred, JSON fallback)
- Dotted key paths for nested config values
- Auto-injected `config get/set/path` subcommands (skipped if app already has `config`)
- Type conflict detection at init and compile time with actionable error messages
- New dependencies: `platformdirs`, `tomlkit`

## 0.1.0 — Usable Core

Initial release. See the [roadmap](getting-started.rst) for what's coming next.
