# Xclif Option System Design

This document defines the option/argument parsing model for Xclif: what syntax is supported, how options interact with subcommand hierarchies, and the rationale for each decision.

---

## Syntax reference

### Long options (primary form)

```
--flag               # boolean flag → True
--name value         # value option, space-separated
--name=value         # value option, = form (TODO: not yet implemented)
```

Long option names use `kebab-case` on the CLI; they map to `snake_case` in Python. `--dry-run` → `dry_run`.

### Short aliases (planned)

```
-v                   # single-char boolean flag
-n value             # single-char value option
```

Short aliases are either auto-generated (first char of the long name, falling back on subsequent chars to avoid collisions) or explicitly declared via `Annotated` metadata. Short options do **not** support bundling (`-abc` ≠ `-a -b -c`) — this is intentional. Bundling is a source of subtle bugs and is rarely needed in modern CLIs.

### Positional arguments

Positional arguments are matched by position against the command's declared parameters. Their order matches the order of parameters in the function signature.

### Interspersed options

Xclif **does** support interspersed options — options and positional arguments may appear in any order relative to each other at the same command level:

```
myapp greet --template "Hi, {}!" Alice
myapp greet Alice --template "Hi, {}!"   # both valid
```

The parser scans all tokens at the current level, collecting positional arguments in order and options by name, regardless of their interleaved position. This matches the behavior users expect from modern CLIs like `git`, `cargo`, and `gh`.

**At a subcommand boundary, interspersing stops.** Once a token is recognized as a subcommand name, everything after it belongs to that subcommand's parser. Options intended for the parent must appear before the subcommand name.

### Option-value disambiguation

A value option consumes the *next token* as its value. This creates an ambiguity when that next token happens to be the name of a known subcommand:

```
myapp config --format json
```

If `json` is also the name of a child subcommand of `config`, how is this parsed?

**Rule: options are greedy.** If `--format` is a value option declared on `config`, the token immediately following it is always consumed as its value — even if that token is a valid subcommand name. The subcommand `json` is not invoked.

```
myapp config --format json        # json is the value of --format
myapp config --format json json   # json is the value of --format; the second json invokes the subcommand
```

This is unambiguous because the parser knows the arity of every option before it starts reading. There is no lookahead needed — if `--format` takes a value, the next token is the value, full stop.

The same rule applies to interspersed positional arguments: tokens are greedily assigned to positional slots in order, and any token that looks like an option (`--`) is always treated as an option.

### The `--` separator (planned)

`--` ends all option parsing. Everything after it is passed as raw positional arguments. This is the POSIX convention and is necessary for commands that invoke subprocesses.

```
myapp run -- --some-flag-for-subprocess
```

---

## Scoping: how options interact with subcommands

### The model: lexical scoping with cascading

Xclif uses **lexical scoping** for options. An option belongs to the command level at which it is declared. The parser reads left to right; when it sees a subcommand name, it hands off the remainder of the token stream to that subcommand's parser.

```
myapp --verbose config --format json set KEY VALUE
  ↑                ↑                 ↑
  root-level       config-level      set-level
  option           option            (positional args)
```

Options parsed at a parent level are **not** passed as kwargs to child commands' `run()` functions — they belong to the parent's scope. However, options declared as **cascading** are forwarded through the call hierarchy as context, not as function arguments (see implementation below).

### Cascading

Cascading options are options whose effect is meaningful at every level below where they are set. The canonical examples are `--verbose`, `--no-color`, and `--dry-run`.

- Cascading is **opt-in per option**, not automatic.
- The implicit options `--verbose` and `--colors` cascade by default.
- User-defined options can be marked cascading via `Annotated` metadata (planned).
- Cascading values are passed as an explicit `cascading: dict` argument down the recursion — no shared state, no thread-locals.

### Default action of parent commands

A parent command (one that has subcommands) can have its own `run` function. This function is invoked when:

1. The user calls the parent with no subcommand and no arguments (e.g. `myapp config` alone).
2. The user explicitly invokes it via flags only (e.g. `myapp config --help`).

If no explicit `run` is defined on a namespace command (i.e. the `__init__.py` defines `@command()` with an empty body), the default action is to **print short help**. This is the most useful default — the user typed a partial command and needs to know what to do next.

This means the lambda `lambda self: self.print_short_help() or 0` used internally as a placeholder for auto-generated namespace nodes is the correct default behavior, not a stub.

A parent command **may** have positional arguments — this is valid as long as the positional arguments are consumed before the subcommand name is seen. In practice this is unusual and confusing; the constraint is enforced by Xclif: **a command cannot declare both positional arguments and subcommands.** The user who needs this pattern should restructure their CLI.

---

## The implicit/cascading option architecture

### The problem with the current implementation

Currently, implicit options (`--help`, `--verbose`, `--colors`, `--version`) are merged directly into `command.options` at `Command.__post_init__` time. This has several problems:

1. They are indistinguishable from user-defined options at parse time.
2. `with_implicit_options` has to intercept them *after* parsing by inspecting `kwargs` — a post-hoc filter rather than a structural separation.
3. They get passed into `command.run()` if the filter doesn't catch them, which breaks user-defined functions that don't expect those kwargs.
4. Cascading is impossible — there's no way to separate "options I parsed for myself" from "options I need to forward."
5. `--version` ends up on every subcommand, not just root.

### The correct model

Implicit and cascading options must be a **separate namespace** from a command's own options. The parser handles them in two passes at each level:

1. **Pre-dispatch pass**: scan for implicit/cascading options at the current level. Act on them immediately (`--help` → print and exit) or store them in the cascading context.
2. **Dispatch pass**: identify and consume positional arguments and user-defined options, then invoke `run()` or recurse into a subcommand — passing only the user-defined kwargs to `run()`.

This means `Command` needs to carry two option dicts:

```python
@dataclass
class Command:
    name: str
    run: Callable[..., int]
    arguments: list[Argument]
    options: dict[str, Option]          # user-defined options only
    implicit_options: dict[str, Option] # help, verbose, colors, version (+ cascading)
    subcommands: dict[str, Command]
```

And `parse_and_execute_impl` receives a `context: dict` of already-resolved cascading values from parent levels:

```python
def parse_and_execute_impl(
    args: list[str],
    command: Command,
    context: dict,        # cascading values resolved by ancestors
) -> int:
    ...
    # 1. Scan for implicit options in args
    # 2. Act on help/version immediately
    # 3. Merge new cascading values into context copy
    # 4. Dispatch: leaf → call run(); namespace → recurse with updated context
```

`run()` only ever receives its own declared kwargs. The context is a separate concern.

---

## Current implementation status

| Feature | Status |
|---|---|
| `--flag` boolean | ✅ Implemented |
| `--name value` (space form) | ✅ Implemented |
| `--name=value` (equals form) | ❌ Not implemented |
| Interspersed options | ❌ Not implemented (options must currently follow positional args) |
| Short options `-v` | ❌ Not implemented |
| `--` separator | ❌ Not implemented |
| Cascading options forwarded to subcommands | ❌ Parsed but silently dropped |
| Implicit options in separate namespace | ❌ Currently merged into `command.options` |
| `--help` triggering help | ✅ Works (via `with_implicit_options` intercept) |
| `-h` triggering short help | ❌ Dead code — short options not parsed |
| `--version` root-only | ❌ Added to every command |
| Repeatable options (`--tag a --tag b` → list) | ✅ Implemented |
| Option bundling (`-abc`) | ✗ Explicitly out of scope |

---

## Open design questions

**Q1: `--version` scoping**
`--version` is in `IMPLICIT_OPTIONS` so it appears on every command. Should it be root-only? **Proposed: yes — strip from subcommands, or make it a `Cli`-level concern rather than a `Command`-level one.**

**Q2: Cascading user options**
Should users be able to declare their own cascading options (e.g. `--dry-run` at root that every subcommand respects)? **Proposed: yes, via `Annotated` metadata in a future milestone. Out of scope for 0.1.0.**

**Q3: Parent command with both a `run` and subcommands**
Is it valid for a parent to have a non-trivial `run` and also have subcommands? E.g. `myapp config` does something useful AND `myapp config set` exists. **Proposed: yes, this is valid and useful. The `run` is the default action when no subcommand is given.**
