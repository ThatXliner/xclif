# Xclif Roadmap

This roadmap is organized by milestone. Each milestone is a shippable, coherent state of the library — not just a list of features.

The current state of the codebase is **pre-alpha**: the core ideas work, but there are known holes, dead code, and TODO comments throughout. The goal is to reach a clean `0.1.0` public release.

---

## Milestone 0: Codebase Cleanup (pre-release)

Before any new features, the existing code needs to be honest about what it does.

- [ ] Remove all dead/commented-out code
- [ ] Remove or quarantine unimplemented stubs (`WithConfig` in `__init__.py:16`, `print_long_help`, completions stub in `__init__.py:42`)
- [ ] Fix `parse_options`: currently passes the raw `arg` string (e.g. `"--verbose"`) into `converter(arg)` instead of the *value* that follows it — this is a bug
- [ ] Fix `print_short_help`: crashes when `arguments`, `subcommands`, and `options` are all empty (passes empty sequences to `max()`)
- [ ] Fix `poetry-clone` experiment: uses `cli.run()` which doesn't exist (should be `cli()`)
- [ ] Clean up `definition.py`: `Option.default` typed as `None | str` but options can have non-string defaults
- [x] Audit all TODOs and decide: implement now, defer to a milestone, or delete
- [ ] Write basic tests for the greeter experiment end-to-end

---

## Milestone 1: `0.1.0` — Usable Core

The minimum the world needs to try Xclif.

**Parsing**
- [ ] Fix option value parsing: `--name Bryan` and `--name=Bryan` both work (`option-system-design.md:14`)
- [ ] Boolean flags: `--verbose` (no value) sets to `True`
- [ ] Short aliases: `-v` for `--verbose` (auto-generated or explicitly declared)
- [ ] Proper error messages: unknown option, missing required argument, wrong type — all with clear, friendly output

**Type support**
- [ ] `str`, `int`, `float`, `bool` all work as argument/option types
- [ ] `list[str]` (and other scalar lists) for repeated options: `--tag foo --tag bar`

**Help**
- [ ] `--help` / `-h` work correctly on every command and subcommand
- [ ] Help text is well-formatted and aligned with `rich`
- [ ] Help text displays option aliases alongside primary names (`command.py:84`)
- [ ] Long description (from full docstring) vs. short description (first line) used correctly

**Routing**
- [ ] `Cli.from_routes()` is stable and well-tested
- [ ] Meaningful errors when routes are malformed (multiple commands per file, missing `__init__.py`, etc.)

**Packaging**
- [ ] `pyproject.toml` filled in (description, license, homepage, classifiers)
- [ ] Published to PyPI

---

## Milestone 2: `0.2.0` — Developer Experience

The things that make Xclif feel polished to use.

**`WithConfig[T]`** (`__init__.py:15-17`)
- [ ] Arguments and options can read from a config file (TOML/JSON in OS data dir)
- [ ] Same parameters can be overridden by environment variables
- [ ] Priority order: CLI flag > env var > config file > default

**Annotations**
- [ ] `Annotated[str, Arg(description="...", alias="-n")]` for per-parameter metadata without leaving the signature
- [ ] Description pulled from `Annotated` metadata for help text

**Error handling**
- [ ] Distinguish user errors (bad CLI invocation) from developer errors (broken command definition) with different output styles
- [ ] Exit codes are correct and documented

**Completions**
- [ ] Shell completion generation for bash, zsh, fish (stub at `__init__.py:42`)

---

## Milestone 3: `0.3.0` — Power Features

For teams building serious CLIs.

**Command overloading / mutual exclusion**
- [ ] `--` separator support for passing raw args to subprocesses
- [ ] Mutually exclusive option groups

**Global options / cascading**
- [ ] Options defined at a parent command level are available to subcommands (e.g. `--verbose` at root flows down)
- [ ] Configurable: opt-in per option, not automatic

**Middleware / hooks**
- [ ] Pre/post command hooks (for auth checks, logging, etc.)

**Plugin system**
- [ ] Third-party type converters via entry points (`annotations.py:8`)
- [ ] Custom implicit options

---

## Non-goals (explicitly out of scope)

- Database access or application-level business logic
- Supporting Python < 3.12 (we use `type` statement, `TypeVarTuple`, etc.)
- A GUI or TUI framework — Xclif is strictly for text CLIs
- Automatic retry, rate limiting, or async execution of commands

---

## Current Known Bugs

| Location | Issue |
|---|---|
| `parser.py:57` | `options[snake_case].converter(arg)` passes the flag name, not the value |
| `command.py:43` | `max()` called on empty sequences when command has no args/subcommands/options |
| `poetry-clone/__main__.py:10` | `cli.run()` should be `cli()` |
| `definition.py:28` | `Option.default: None \| str` should be `Any` |
| `__init__.py:51` | Lambda captures `self` but `Command.__init__` doesn't take `self` as an arg |
