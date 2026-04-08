"""Tests for completions command."""
import sys
from unittest.mock import patch

import pytest

from xclif.command import Command
from xclif.completions import generate_bash, generate_fish, generate_zsh, make_completions_command


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


# ---------------------------------------------------------------------------
# Alias handling in completion scripts
# ---------------------------------------------------------------------------


@pytest.fixture
def root_with_alias():
    child = Command("greet", lambda: 0, aliases=["g"])
    root = Command("myapp", lambda: 0, subcommands={"greet": child, "g": child})
    return root


def test_bash_completions_include_alias_as_candidate(root_with_alias):
    script = generate_bash(root_with_alias)
    # "g" should appear in the word list so tab-completing "g" works
    assert " g " in script or ' g"' in script


def test_bash_completions_no_duplicate_case_entry(root_with_alias):
    script = generate_bash(root_with_alias)
    # A single combined case pattern matching both canonical name and alias
    assert "greet|g)" in script
    assert script.count("greet|g)") == 1


def test_zsh_completions_include_alias_as_candidate(root_with_alias):
    script = generate_zsh(root_with_alias)
    assert "'g:" in script


def test_fish_completions_include_alias_as_candidate(root_with_alias):
    script = generate_fish(root_with_alias)
    assert " -a 'g'" in script
