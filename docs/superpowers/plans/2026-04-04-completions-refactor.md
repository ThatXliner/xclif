# Completions Refactor + Literal Type Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `Literal["a", "b", ...]` type support to xclif and refactor the `completions` command from per-shell subcommands to a single command with a positional `shell` argument.

**Architecture:** `annotation2converter` in `annotations.py` gains a Literal branch that returns a validating converter; `Argument` gains an optional `choices` field for help display; `make_completions_command` is rewritten as a leaf command with `shell: Literal["bash", "zsh", "fish"]`.

**Tech Stack:** Python 3.12, `typing.Literal`, `typing.get_origin/get_args`, rich (for stderr hint), pytest

---

## File Map

| File | Change |
|------|--------|
| `src/xclif/annotations.py` | Add Literal branch to `annotation2converter` |
| `src/xclif/definition.py` | Add `choices: list[str] \| None = None` field to `Argument` |
| `src/xclif/command.py` | Use `arg.choices` in help display instead of bare name |
| `src/xclif/completions.py` | Rewrite `make_completions_command` |
| `tests/test_annotations.py` | New file — Literal converter tests |
| `tests/test_completions.py` | New file — completions command tests |
| `tests/test_command.py` | Add Literal extract_parameters tests |

---

### Task 1: Literal support in `annotation2converter`

**Files:**
- Modify: `src/xclif/annotations.py`
- Create: `tests/test_annotations.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_annotations.py`:

```python
"""Unit tests for xclif.annotations."""
import pytest
from typing import Literal
from xclif.annotations import annotation2converter


def test_literal_converter_accepts_valid_value():
    conv = annotation2converter(Literal["bash", "zsh", "fish"])
    assert conv("bash") == "bash"
    assert conv("zsh") == "zsh"
    assert conv("fish") == "fish"


def test_literal_converter_rejects_invalid_value():
    conv = annotation2converter(Literal["bash", "zsh", "fish"])
    with pytest.raises(ValueError, match="bash.*zsh.*fish"):
        conv("powershell")


def test_literal_returns_none_for_mixed_types():
    # Mixed-type Literals are not supported — annotation2converter returns None
    result = annotation2converter(Literal["a", 1])
    assert result is None


def test_literal_single_value():
    conv = annotation2converter(Literal["only"])
    assert conv("only") == "only"


def test_non_literal_unchanged():
    assert annotation2converter(str) is str
    assert annotation2converter(int) is int
```

- [ ] **Step 2: Run tests to verify they fail**

```
uv run python -m pytest tests/test_annotations.py -v
```

Expected: FAIL — `annotation2converter` returns `None` for Literal types.

- [ ] **Step 3: Implement Literal branch in `annotation2converter`**

In `src/xclif/annotations.py`, replace the `annotation2converter` function:

```python
from typing import Annotated, Callable, Literal, get_args, get_origin

type ScalarParameterTypes = str | int | float | bool
type ParameterTypes = ScalarParameterTypes | list[ScalarParameterTypes]
_default_converters = {str: str, int: int, float: float, bool: bool}


def annotation2converter[T: ParameterTypes, Y](x: T) -> None | Callable[[T], Y]:
    # Check for list[X] generics (e.g. list[str], list[int])
    origin = get_origin(x)
    if origin is list:
        args = get_args(x)
        if args and args[0] in _default_converters:
            return _default_converters[args[0]]
        return None
    if origin is Literal:
        choices = get_args(x)
        # Only support all-string Literals
        if not all(isinstance(c, str) for c in choices):
            return None
        choices_set = set(choices)
        choices_str = "|".join(choices)
        def _literal_converter(value: str, _choices=choices_set, _str=choices_str) -> str:
            if value not in _choices:
                raise ValueError(f"expected one of: {_str}, got {value!r}")
            return value
        _literal_converter.__choices__ = list(choices)  # store for help display
        return _literal_converter
    return _default_converters.get(x)
```

- [ ] **Step 4: Run tests to verify they pass**

```
uv run python -m pytest tests/test_annotations.py -v
```

Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/xclif/annotations.py tests/test_annotations.py
git commit -m "feat(annotations): add Literal type support to annotation2converter"
```

---

### Task 2: `choices` field on `Argument` + help display

**Files:**
- Modify: `src/xclif/definition.py`
- Modify: `src/xclif/command.py`
- Modify: `tests/test_command.py`

- [ ] **Step 1: Write failing tests for `extract_parameters` with Literal**

Add to `tests/test_command.py`:

```python
from typing import Literal


def test_literal_argument_has_choices():
    def f(shell: Literal["bash", "zsh", "fish"]) -> None: ...
    args, opts = extract_parameters(f)
    assert len(args) == 1
    assert args[0].choices == ["bash", "zsh", "fish"]


def test_literal_argument_converter_validates():
    from xclif.errors import UsageError
    def f(shell: Literal["bash", "zsh", "fish"]) -> None: ...
    args, _ = extract_parameters(f)
    assert args[0].converter("bash") == "bash"
    with pytest.raises(ValueError):
        args[0].converter("nope")


def test_literal_option_has_choices():
    def f(shell: Literal["bash", "zsh"] = "bash") -> None: ...
    _, opts = extract_parameters(f)
    assert opts["shell"].choices == ["bash", "zsh"]
```

- [ ] **Step 2: Run to verify they fail**

```
uv run python -m pytest tests/test_command.py::test_literal_argument_has_choices tests/test_command.py::test_literal_argument_converter_validates tests/test_command.py::test_literal_option_has_choices -v
```

Expected: FAIL — `Argument` has no `choices` attribute.

- [ ] **Step 3: Add `choices` field to `Argument` and `Option` in `definition.py`**

```python
@dataclass
class Argument[T]:
    name: str
    converter: Callable[[Any], T]
    description: str
    variadic: bool = False
    config: WithConfig | None = None
    choices: list[str] | None = None

    @property
    def short_description(self) -> str:
        return self.description.splitlines()[0]


@dataclass
class Option[T]:
    name: str
    converter: Callable[[Any], T]
    description: str
    default: Any = None
    cascading: bool = False
    is_list: bool = False
    aliases: list[str] = field(default_factory=list)
    config: WithConfig | None = None
    choices: list[str] | None = None

    @property
    def short_description(self) -> str:
        return self.description.splitlines()[0]
```

- [ ] **Step 4: Populate `choices` in `extract_parameters` in `command.py`**

In `extract_parameters`, after computing `converter`, extract choices if it's a Literal converter. Add this helper at module level in `command.py`:

```python
def _get_choices(converter) -> list[str] | None:
    """Return choices list if converter is a Literal converter, else None."""
    return getattr(converter, "__choices__", None)
```

Then in the `is_argument` branch, update the `Argument` construction:

```python
arguments.append(Argument(
    display_name, converter, description,
    config=with_config,
    choices=_get_choices(converter),
))
```

And in the `else` (option) branch, update the `Option` construction:

```python
options[name] = Option(
    cli_name, converter, description, default,
    is_list=list_valued, aliases=aliases, config=with_config,
    choices=_get_choices(converter),
)
```

- [ ] **Step 5: Run tests to verify they pass**

```
uv run python -m pytest tests/test_command.py -v
```

Expected: All tests PASS including the 3 new ones.

- [ ] **Step 6: Update help display in `command.py` to show `[bash|zsh|fish]`**

In `print_short_help` and `print_long_help`, arguments are rendered with their `name`. Update to use choices when present. Both methods have a block like:

```python
" ".join(
    f"[{x.name.upper()}{'...' if x.variadic else ''}]"
    for x in self.arguments
)
```

Replace both occurrences with:

```python
" ".join(
    f"[{'|'.join(x.choices) if x.choices else x.name.upper()}{'...' if x.variadic else ''}]"
    for x in self.arguments
)
```

Also in the Arguments section of help, the label `[{x.name}...]` should show choices:

```python
f"[b][{'|'.join(x.choices) if x.choices else x.name}{'...' if x.variadic else ''}][/b]"
```

- [ ] **Step 7: Commit**

```bash
git add src/xclif/definition.py src/xclif/command.py tests/test_command.py
git commit -m "feat(definition,command): add choices field for Literal arguments and update help display"
```

---

### Task 3: Rewrite `make_completions_command`

**Files:**
- Modify: `src/xclif/completions.py`
- Create: `tests/test_completions.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_completions.py`:

```python
"""Tests for completions command."""
import sys
from io import StringIO
from unittest.mock import patch

import pytest

from xclif.command import Command
from xclif.completions import make_completions_command


@pytest.fixture
def root():
    def _root() -> int:
        """My app."""
    cmd = Command("myapp", _root)
    return cmd


def test_completions_is_single_command_not_subcommands(root):
    comp = make_completions_command(root)
    assert comp.name == "completions"
    assert comp.subcommands == {}
    assert len(comp.arguments) == 1
    assert comp.arguments[0].choices == ["bash", "zsh", "fish"]


def test_completions_bash_prints_script(root, capsys):
    comp = make_completions_command(root)
    with patch("sys.stdout.isatty", return_value=False):
        result = comp.run("bash")
    captured = capsys.readouterr()
    assert "myapp" in captured.out
    assert "_complete_myapp" in captured.out
    assert result == 0


def test_completions_zsh_prints_script(root, capsys):
    comp = make_completions_command(root)
    with patch("sys.stdout.isatty", return_value=False):
        result = comp.run("zsh")
    captured = capsys.readouterr()
    assert "#compdef myapp" in captured.out
    assert result == 0


def test_completions_fish_prints_script(root, capsys):
    comp = make_completions_command(root)
    with patch("sys.stdout.isatty", return_value=False):
        result = comp.run("fish")
    captured = capsys.readouterr()
    assert "# Completions for myapp" in captured.out
    assert result == 0


def test_completions_tty_prints_hint_to_stderr(root, capsys):
    comp = make_completions_command(root)
    with patch("sys.stdout.isatty", return_value=True):
        comp.run("zsh")
    captured = capsys.readouterr()
    assert "~/.zsh/completions/_myapp" in captured.err


def test_completions_no_tty_no_stderr_hint(root, capsys):
    comp = make_completions_command(root)
    with patch("sys.stdout.isatty", return_value=False):
        comp.run("bash")
    captured = capsys.readouterr()
    assert captured.err == ""


def test_completions_bash_hint_path(root, capsys):
    comp = make_completions_command(root)
    with patch("sys.stdout.isatty", return_value=True):
        comp.run("bash")
    captured = capsys.readouterr()
    assert "~/.local/share/bash-completion/completions/myapp" in captured.err


def test_completions_fish_hint_path(root, capsys):
    comp = make_completions_command(root)
    with patch("sys.stdout.isatty", return_value=True):
        comp.run("fish")
    captured = capsys.readouterr()
    assert "~/.config/fish/completions/myapp.fish" in captured.err
```

- [ ] **Step 2: Run to verify they fail**

```
uv run python -m pytest tests/test_completions.py -v
```

Expected: Most tests FAIL — `make_completions_command` still uses subcommands.

- [ ] **Step 3: Rewrite `make_completions_command`**

Replace `make_completions_command` in `src/xclif/completions.py`:

```python
def make_completions_command(root: Command) -> "Command":
    """Build the completions subcommand."""
    from typing import Literal
    import sys
    import rich
    from xclif.command import Command, extract_parameters

    _INSTALL_HINTS = {
        "bash": "~/.local/share/bash-completion/completions/{app}",
        "zsh": "~/.zsh/completions/_{app}",
        "fish": "~/.config/fish/completions/{app}.fish",
    }

    def completions_run(shell: Literal["bash", "zsh", "fish"]) -> int:
        """Generate shell completion script

        Prints the completion script for SHELL to stdout.
        Pipe it to the appropriate location for your shell.
        """
        generators = {
            "bash": generate_bash,
            "zsh": generate_zsh,
            "fish": generate_fish,
        }
        script = generators[shell](root)
        print(script, end="")
        if sys.stdout.isatty():
            path = _INSTALL_HINTS[shell].format(app=root.name)
            rich.print(
                f"[dim]# To install, run:[/dim]\n"
                f"[bold]  {root.name} completions {shell} > {path}[/bold]",
                file=sys.stderr,
            )
        return 0

    from xclif.command import extract_parameters
    arguments, options = extract_parameters(completions_run)
    return Command("completions", completions_run, arguments, options)
```

- [ ] **Step 4: Run tests to verify they pass**

```
uv run python -m pytest tests/test_completions.py -v
```

Expected: All 8 tests PASS.

- [ ] **Step 5: Run full test suite to check for regressions**

```
uv run python -m pytest -v
```

Expected: All tests PASS. Pay attention to `test_cli.py::test_cli_auto_adds_completions_command` — it only checks that `"completions"` is in subcommands, which still holds.

- [ ] **Step 6: Commit**

```bash
git add src/xclif/completions.py tests/test_completions.py
git commit -m "feat(completions): replace per-shell subcommands with single positional-arg command"
```

---

### Task 4: Update existing completions test in `test_cli.py`

The existing test `test_cli_auto_adds_completions_command` only checks that `"completions"` is in subcommands — it will still pass. But add one more test to assert the new shape.

**Files:**
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Add test for new completions shape**

Add to `tests/test_cli.py`:

```python
def test_cli_completions_is_single_command_with_shell_arg():
    root = Command("myapp", lambda: 0)
    cli = Cli(root_command=root)
    comp = cli.root_command.subcommands["completions"]
    assert comp.subcommands == {}
    assert len(comp.arguments) == 1
    assert comp.arguments[0].choices == ["bash", "zsh", "fish"]
```

- [ ] **Step 2: Run to verify it passes**

```
uv run python -m pytest tests/test_cli.py -v
```

Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_cli.py
git commit -m "test(cli): assert completions command uses positional shell arg"
```
