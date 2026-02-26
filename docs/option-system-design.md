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

### Variadic positional arguments (planned)

The last positional parameter may be variadic — consuming all remaining non-option tokens. In Python this maps to `*args`:

```python
@command()
def add(*files: str) -> None:
    """Stage files for commit."""
    for f in files:
        stage(f)
```

```
myapp add file1.py file2.py file3.py   # files = ("file1.py", "file2.py", "file3.py")
```

**Variadic positionals and subcommands are mutually exclusive.** A command that declares a variadic positional would swallow any subcommand name as a positional value — there is no way to disambiguate. Xclif enforces this at definition time (`Cli.from_routes` / `add_command`), not at parse time:

- If a command declares a variadic positional parameter, it **cannot** have subcommands.
- If a route module has child modules (subcommands), its command **cannot** declare a variadic positional.
- Violation of either rule is a definition-time error with a clear message.

This is the same constraint Xclif already enforces for regular positional arguments + subcommands, extended to the variadic case.

Fixed-arity positional arguments on a leaf command are fine — they consume exactly N tokens and stop.

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

### Why not `nargs='*'` / `nargs='+'` on options?

argparse supports variadic options — `--files` consuming an unbounded number of following tokens. Xclif does **not** support this on options, by design.

**The problem:** variadic options introduce genuine ambiguity. `--files a b c --verbose` — where does the list end? argparse uses heuristics (anything starting with `-` terminates the list), which means `--files -1 2 3` breaks because `-1` looks like a flag. It's a footgun that gets worse in structured CLIs where subcommand names are also valid tokens.

**The alternatives cover every real-world case:**

1. **Repeated options:** `--tag foo --tag bar` → `["foo", "bar"]`. Unambiguous, composable, already implemented.
2. **Comma-separated values:** `--tags foo,bar` → single token, split by the converter. Zero ambiguity.
3. **Variadic positional args:** `myapp add file1 file2 file3` → the `*args` pattern on the last positional. Fine because by the time you're in a leaf command, subcommand names aren't in play.

Well-designed modern CLIs use these patterns exclusively. `docker run -e FOO=bar -e BAZ=qux` (repeated), `cargo build --features feat1,feat2` (comma-sep), `git add file1 file2` (variadic positional). None of them use argparse-style variadic options.

Variadic options are a historic artifact from single-command scripts. In structured CLIs with subcommand hierarchies, they break the left-to-right unambiguous parsing model that Xclif depends on.

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
- Cascading values are passed as an explicit `context: dict` argument down the recursion — no shared state, no thread-locals.

### Default action of parent commands

A parent command (one that has subcommands) can have its own `run` function. This function is invoked when:

1. The user calls the parent with no subcommand and no arguments (e.g. `myapp config` alone).
2. The user explicitly invokes it via flags only (e.g. `myapp config --help`).

If no explicit `run` is defined on a namespace command (i.e. the `__init__.py` defines `@command()` with an empty body), the default action is to **print short help**. This is the most useful default — the user typed a partial command and needs to know what to do next.

A parent command **cannot** declare both positional arguments and subcommands. This is enforced at definition time.

---

## The implicit/cascading option architecture

Implicit options (`--help`, `--verbose`, `--colors`, `--version`) live in a **separate namespace** (`Command.implicit_options`) from user-defined options (`Command.options`). They are never forwarded as kwargs to `run()`.

The parser handles them in a single scan alongside user options (since `_parse_token_stream` needs to know the arity of every option), but the dispatch logic separates them:

1. **Pre-dispatch:** act on `--help` and `--version` immediately (print and return 0).
2. **Cascading:** merge cascading implicit values into a `context: dict` passed down the recursion.
3. **Dispatch:** call `run()` with only user-defined kwargs, or recurse into a subcommand with the updated context.

```python
@dataclass
class Command:
    name: str
    run: Callable[..., int]
    arguments: list[Argument]
    options: dict[str, Option]          # user-defined options only
    implicit_options: dict[str, Option] # help, verbose, colors, version
    subcommands: dict[str, Command]
```

---

## Current implementation status

| Feature | Status |
|---|---|
| `--flag` boolean | ✅ |
| `--name value` (space form) | ✅ |
| `--name=value` (equals form) | ❌ |
| Interspersed options | ✅ |
| Short options `-v` | ❌ |
| `--` separator | ❌ |
| Implicit options in separate namespace | ✅ |
| `--help` triggering help | ✅ |
| Cascading context passed to subcommands | ✅ |
| Cascading values not leaked to `run()` | ✅ |
| Repeatable options (`--tag a --tag b` → list) | ✅ |
| Variadic positional `*args` | ❌ |
| `--version` root-only | ❌ (added to every command) |
| Variadic options (`nargs='*'`/`'+'`) | ✗ Explicitly out of scope |
| Option bundling (`-abc`) | ✗ Explicitly out of scope |

---

## Open design questions

**Q1: `--version` scoping**
`--version` is in `IMPLICIT_OPTIONS` so it appears on every command. Should it be root-only? **Proposed: yes — make it a `Cli`-level concern rather than a `Command`-level one.**

**Q2: Cascading user options**
Should users be able to declare their own cascading options (e.g. `--dry-run` at root that every subcommand respects)? **Proposed: yes, via `Annotated` metadata in a future milestone. Out of scope for 0.1.0.**

**Q3: Parent command with both a `run` and subcommands**
Is it valid for a parent to have a non-trivial `run` and also have subcommands? E.g. `myapp config` does something useful AND `myapp config set` exists. **Proposed: yes, this is valid and useful. The `run` is the default action when no subcommand is given.**
