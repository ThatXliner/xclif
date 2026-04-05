# Design: Completions Refactor + Literal Type Support

## Summary

Two related changes:
1. Add `Literal["a", "b", ...]` support to xclif's annotation/converter system
2. Refactor the `completions` command from sub-subcommands-per-shell to a single command with a `Literal`-typed positional argument

---

## 1. Literal Type Support

**File:** `src/xclif/annotations.py`

`annotation2converter` gains a new branch: if `get_origin(x) is Literal`, extract the literal args (all must be strings), and return a converter that validates the input is one of those values, raising `ValueError` on an unknown value. xclif's existing error handling catches `ValueError` and surfaces it as a `UsageError`.

**Help display:** When an `Argument` or `Option` is backed by a `Literal` type, the valid choices are shown inline in help output — e.g. `[bash|zsh|fish]` instead of a generic `SHELL` display name. This requires passing choice information through to `Argument`/`Option` or deriving it at display time from the converter.

**Constraints:**
- Only `Literal` of strings is supported (matching what CLI arguments are)
- Mixed-type Literals (e.g. `Literal["a", 1]`) raise `TypeError` at command construction time

---

## 2. Completions Command Restructure

**File:** `src/xclif/completions.py`

`make_completions_command` is rewritten. The three sub-subcommands (`bash`, `zsh`, `fish`) are replaced with a single `completions` command that takes one required positional argument `shell: Literal["bash", "zsh", "fish"]`.

**Run logic:**
1. Dispatch to `generate_bash`, `generate_zsh`, or `generate_fish` based on `shell`
2. Print the generated script to stdout
3. If `sys.stdout.isatty()`: print a colored install hint to stderr using rich, showing the shell-specific recommended destination:
   - `bash`: `~/.local/share/bash-completion/completions/<app>`
   - `zsh`: `~/.zsh/completions/_<app>`
   - `fish`: `~/.config/fish/completions/<app>.fish`

**Hint format (stderr, TTY only):**
```
[dim]# To install, run:[/dim]
[bold]  mycli completions zsh > ~/.zsh/completions/_mycli[/bold]
```

**Deleted:** `bash_run`, `zsh_run`, `fish_run` inner functions and the `subcommands={...}` dict are removed entirely.

---

## Files Changed

| File | Change |
|------|--------|
| `src/xclif/annotations.py` | Add `Literal` branch to `annotation2converter`; update `is_list_type` if needed |
| `src/xclif/completions.py` | Rewrite `make_completions_command` to single command with positional arg |

No other files require changes. The `Argument` display logic in `command.py` may need a small update to render `[bash|zsh|fish]` for Literal-typed arguments.
