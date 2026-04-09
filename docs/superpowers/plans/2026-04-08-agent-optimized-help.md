# Agent-Optimized Help Output — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Auto-detect non-TTY output and emit a hyper-short, token-efficient help format optimized for LLM agents.

**Architecture:** Add `print_agent_help()` to `Command` that recursively flattens the command tree into a compact format. Gate `print_short_help()` and `print_long_help()` with `Console().is_terminal` to auto-dispatch. Update benchmarks to set `FORCE_COLOR=1` so `--help` benchmarks remain fair.

**Tech Stack:** Python, Rich (for TTY detection via `Console.is_terminal`)

**Spec:** `docs/superpowers/specs/2026-04-08-agent-optimized-help-design.md`

---

### Task 1: Add `print_agent_help()` method with tests

**Files:**
- Modify: `src/xclif/command.py:26-45` (add method to `Command` class)
- Test: `tests/test_command.py`

- [ ] **Step 1: Write failing test for basic agent help output**

In `tests/test_command.py`, add at the end:

```python
# ---------------------------------------------------------------------------
# Command.print_agent_help — agent-optimized output
# ---------------------------------------------------------------------------


def test_agent_help_leaf_command_no_options(capsys):
    """Leaf command with no user options prints name: description only."""
    cmd = Command("mytool", lambda: 0)
    cmd.run.__doc__ = "A simple tool."
    cmd.print_agent_help()
    out = capsys.readouterr().out
    assert out == "mytool: A simple tool.\n"


def test_agent_help_leaf_command_with_options(capsys):
    """Leaf command with user options lists them inline."""
    @command()
    def mytool(name: str = "", count: int = 3, dry_run: bool = False) -> None:
        """A tool with options."""

    mytool.print_agent_help()
    out = capsys.readouterr().out
    assert "mytool: A tool with options." in out
    assert "--name STR" in out
    assert '--count INT (default: 3)' in out
    assert "--dry-run" in out
    # Should NOT contain implicit framework options
    assert "--help" not in out
    assert "--colors" not in out


def test_agent_help_flattens_subcommands(capsys):
    """Subcommands are flattened with full path."""
    root = Command("app", lambda: 0)
    root.run.__doc__ = "My app."

    @command()
    def sub1() -> None:
        """First sub."""

    @command()
    def sub2(target: str = "") -> None:
        """Second sub."""

    root.subcommands["sub1"] = sub1
    root.subcommands["sub2"] = sub2

    root.print_agent_help()
    out = capsys.readouterr().out
    assert "app: My app." in out
    assert "sub1 - First sub." in out
    assert "sub2 - Second sub." in out
    assert "--target STR" in out


def test_agent_help_flattens_nested_subcommands(capsys):
    """Nested subcommands produce flattened paths like 'config get'."""
    root = Command("app", lambda: 0)
    root.run.__doc__ = "My app."

    group = Command("config", lambda: 0)
    group.run.__doc__ = "Manage config."

    @command()
    def get() -> None:
        """Print config."""

    @command()
    def set_cmd() -> None:
        """Set config."""

    group.subcommands["get"] = get
    group.subcommands["set"] = set_cmd
    root.subcommands["config"] = group

    root.print_agent_help()
    out = capsys.readouterr().out
    assert "config get - Print config." in out
    assert "config set" in out
    # The group itself should not appear as a separate line
    lines = [l for l in out.strip().split("\n") if l.startswith("config -")]
    assert lines == []


def test_agent_help_hides_completions_subcommand(capsys):
    """Framework subcommand 'completions' is filtered out."""
    root = Command("app", lambda: 0)
    root.run.__doc__ = "My app."

    @command()
    def real() -> None:
        """A real command."""

    completions = Command("completions", lambda: 0)
    completions.run.__doc__ = "Generate completions."

    root.subcommands["real"] = real
    root.subcommands["completions"] = completions

    root.print_agent_help()
    out = capsys.readouterr().out
    assert "real - A real command." in out
    assert "completions" not in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_command.py -k "agent_help" -v`
Expected: FAIL with `AttributeError: 'Command' object has no attribute 'print_agent_help'`

- [ ] **Step 3: Implement `print_agent_help()` on `Command`**

In `src/xclif/command.py`, add the module-level constant after the existing imports (around line 12):

```python
_AGENT_HIDDEN_SUBCOMMANDS = {"completions"}
```

Then add the method to the `Command` class (after `print_long_help`, around line 204):

```python
    def print_agent_help(self) -> None:
        """Print a hyper-short, token-efficient help summary for LLM agents.

        Recursively flattens the entire command tree. Filters out framework-owned
        implicit options and hidden subcommands like ``completions``.
        """
        print(f"{self.name}: {self.short_description}")
        lines = _collect_agent_lines(self, prefix="")
        if lines:
            print()
            print("\n".join(lines))
```

Then add the module-level helper functions (after the `_arg_section_label` function, around line 284):

```python
def _collect_agent_lines(cmd: Command, prefix: str) -> list[str]:
    """Recursively collect flattened command lines for agent help."""
    lines: list[str] = []
    for name, sub in cmd.subcommands.items():
        if name != sub.name:  # skip alias entries
            continue
        if name in _AGENT_HIDDEN_SUBCOMMANDS:
            continue
        path = f"{prefix}{name}" if prefix else name
        if sub.subcommands:
            # Non-leaf: recurse, don't emit a line for the group itself
            lines.extend(_collect_agent_lines(sub, path + " "))
        else:
            # Leaf command
            line = f"{path} - {sub.short_description}"
            opts = _format_agent_options(sub)
            if opts:
                line += f" Options: {opts}"
            lines.append(line)
    return lines


def _format_agent_options(cmd: Command) -> str:
    """Format user-defined options for agent help output."""
    parts: list[str] = []
    for name, opt in cmd.options.items():
        flag = f"--{opt.name.replace('_', '-')}"
        if opt.converter is bool:
            parts.append(flag)
        else:
            type_name = opt.converter.__name__.upper()
            part = f"{flag} {type_name}"
            if opt.default is not None and opt.default != "":
                part += f" (default: {opt.default!r})"
            parts.append(part)
    return ", ".join(parts)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_command.py -k "agent_help" -v`
Expected: All 5 new tests PASS

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest`
Expected: All tests pass (no regressions)

- [ ] **Step 6: Commit**

```bash
git add src/xclif/command.py tests/test_command.py
git commit -m "feat: add print_agent_help() for token-efficient LLM help output"
```

---

### Task 2: Add TTY detection guard to `print_short_help()` and `print_long_help()`

**Files:**
- Modify: `src/xclif/command.py:71-72` (`print_short_help`) and `src/xclif/command.py:134-135` (`print_long_help`)
- Test: `tests/test_command.py`

- [ ] **Step 1: Write failing test for TTY dispatch**

In `tests/test_command.py`, add:

```python
def test_print_short_help_dispatches_agent_when_not_tty(capsys, monkeypatch):
    """print_short_help uses agent format when Console reports non-TTY."""
    monkeypatch.setattr("xclif.command._get_console", lambda **kw: type("C", (), {"is_terminal": False})())
    root = Command("app", lambda: 0)
    root.run.__doc__ = "My app."

    @command()
    def sub() -> None:
        """A sub."""

    root.subcommands["sub"] = sub
    root.print_short_help()
    out = capsys.readouterr().out
    # Should be agent format (no Rich markup, flattened)
    assert "app: My app." in out
    assert "sub - A sub." in out
    assert "[b]" not in out


def test_print_long_help_dispatches_agent_when_not_tty(capsys, monkeypatch):
    """print_long_help uses agent format when Console reports non-TTY."""
    monkeypatch.setattr("xclif.command._get_console", lambda **kw: type("C", (), {"is_terminal": False})())

    @command()
    def mytool(name: str) -> None:
        """A tool."""

    mytool.print_long_help()
    out = capsys.readouterr().out
    assert "mytool: A tool." in out
    assert "[b]" not in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_command.py -k "dispatches_agent" -v`
Expected: FAIL — output contains Rich markup because no TTY guard exists yet

- [ ] **Step 3: Add TTY guard to both methods**

In `src/xclif/command.py`, add at the top of `print_short_help()` (line 72):

```python
    def print_short_help(self) -> None:
        """Print a compact one-screen help summary to stdout."""
        if not _get_console().is_terminal:
            self.print_agent_help()
            return
        all_options = {**self.implicit_options, **self.options}
```

And at the top of `print_long_help()` (line 135):

```python
    def print_long_help(self) -> None:
        """Print the full help page (including the long description) to stdout."""
        if not _get_console().is_terminal:
            self.print_agent_help()
            return
        from rich.markdown import Markdown
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_command.py -k "dispatches_agent" -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add src/xclif/command.py tests/test_command.py
git commit -m "feat: auto-detect non-TTY and dispatch agent help format"
```

---

### Task 3: Update benchmarks to set `FORCE_COLOR=1`

**Files:**
- Modify: `benchmarks/bench_frameworks.py:113-122` (`run_once` function)
- Modify: `benchmarks/bench_frameworks.sh:36-43` (`run` function)

- [ ] **Step 1: Update `bench_frameworks.py`**

In `benchmarks/bench_frameworks.py`, modify `run_once` (line 113):

```python
def run_once(cmd: list[str], args: list[str]) -> float:
    """Invoke the command, return elapsed milliseconds."""
    t0 = time.perf_counter()
    subprocess.run(
        cmd + args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=EXAMPLES_DIR,
        env={**os.environ, "FORCE_COLOR": "1"},
    )
    return (time.perf_counter() - t0) * 1000
```

Also add `import os` at the top of the file (after `import argparse`, line 13):

```python
import os
```

- [ ] **Step 2: Update `bench_frameworks.sh`**

In `benchmarks/bench_frameworks.sh`, update the xclif command definitions (lines 35-36) to include `FORCE_COLOR=1`:

```bash
XCLIF="env FORCE_COLOR=1 PYTHONPATH=$DIR $PY -m xclif_greeter"
XCLIF_MANIFEST="env FORCE_COLOR=1 PYTHONPATH=$DIR $PY -m xclif_greeter_manifest"
```

And add it to the flat variant too (line 34):

```bash
XCLIF_FLAT="env FORCE_COLOR=1 $PY $DIR/xclif_greeter_flat.py"
```

- [ ] **Step 3: Commit**

```bash
git add benchmarks/bench_frameworks.py benchmarks/bench_frameworks.sh
git commit -m "fix(benchmarks): set FORCE_COLOR=1 so --help benchmarks measure Rich output"
```
