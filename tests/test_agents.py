"""Tests for agent detection."""

import pytest
from xclif import agents as agents_module
from xclif.agents import (
    ANTIGRAVITY,
    AUGMENT_CLI,
    CLAUDE,
    CODEX,
    COWORK,
    CURSOR,
    CURSOR_CLI,
    DEVIN,
    GEMINI,
    GITHUB_COPILOT,
    OPENCODE,
    REPLIT,
    V0,
    determine_agent,
    is_agent,
)


_AGENT_ENV_VARS = [
    "AI_AGENT",
    "CURSOR_TRACE_ID",
    "CURSOR_AGENT",
    "CURSOR_EXTENSION_HOST_ROLE",
    "GEMINI_CLI",
    "CODEX_SANDBOX",
    "CODEX_CI",
    "CODEX_THREAD_ID",
    "ANTIGRAVITY_AGENT",
    "AUGMENT_AGENT",
    "OPENCODE_CLIENT",
    "CLAUDECODE",
    "CLAUDE_CODE",
    "CLAUDE_CODE_IS_COWORK",
    "REPL_ID",
    "COPILOT_MODEL",
    "COPILOT_ALLOW_ALL",
    "COPILOT_GITHUB_TOKEN",
]


@pytest.fixture(autouse=True)
def isolate_agent_detection(monkeypatch):
    """Keep host agent environment variables from affecting expectations."""
    for var in _AGENT_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(agents_module.os, "access", lambda *_args: False)


def test_no_agent_by_default():
    """Without agent env vars, should return False."""
    assert determine_agent() == (False, None)
    assert is_agent() is False


def test_ai_agent_env_var(monkeypatch):
    """AI_AGENT env var should be detected."""
    monkeypatch.setenv("AI_AGENT", "custom-agent")
    assert determine_agent() == (True, "custom-agent")


def test_ai_agent_strips_and_detects_v0(monkeypatch):
    """AI_AGENT should normalize whitespace and detect v0 explicitly."""
    monkeypatch.setenv("AI_AGENT", "  v0  ")
    assert determine_agent() == (True, V0)


def test_blank_ai_agent_falls_through(monkeypatch):
    """A whitespace-only AI_AGENT value should not count as an agent."""
    monkeypatch.setenv("AI_AGENT", "   ")
    assert determine_agent() == (False, None)


def test_claude_code_env_var(monkeypatch):
    """CLAUDE_CODE env var should detect Claude."""
    monkeypatch.setenv("CLAUDE_CODE", "1")
    monkeypatch.delenv("CLAUDE_CODE_IS_COWORK", raising=False)
    assert determine_agent() == (True, CLAUDE)


def test_claude_code_cowork(monkeypatch):
    """CLAUDE_CODE with CLAUDE_CODE_IS_COWORK should detect Cowork."""
    monkeypatch.setenv("CLAUDE_CODE", "1")
    monkeypatch.setenv("CLAUDE_CODE_IS_COWORK", "1")
    assert determine_agent() == (True, COWORK)


def test_cursor_trace_id(monkeypatch):
    """CURSOR_TRACE_ID env var should detect Cursor."""
    monkeypatch.delenv("AI_AGENT", raising=False)
    monkeypatch.setenv("CURSOR_TRACE_ID", "abc123")
    assert determine_agent() == (True, CURSOR)


def test_gemini_cli(monkeypatch):
    """GEMINI_CLI env var should detect Gemini."""
    monkeypatch.setenv("GEMINI_CLI", "1")
    assert determine_agent() == (True, GEMINI)


def test_codex_sandbox(monkeypatch):
    """CODEX_SANDBOX env var should detect Codex."""
    monkeypatch.setenv("CODEX_SANDBOX", "1")
    assert determine_agent() == (True, CODEX)


@pytest.mark.parametrize("env_var", ["CODEX_CI", "CODEX_THREAD_ID"])
def test_codex_alternate_env_vars(monkeypatch, env_var):
    """Other Codex env vars should also detect Codex."""
    monkeypatch.setenv(env_var, "1")
    assert determine_agent() == (True, CODEX)


@pytest.mark.parametrize(
    ("env_var", "value"),
    [
        ("CURSOR_AGENT", "1"),
        ("CURSOR_EXTENSION_HOST_ROLE", "agent-exec"),
    ],
)
def test_cursor_cli_env_vars(monkeypatch, env_var, value):
    """Cursor CLI env vars should detect the CLI agent."""
    monkeypatch.setenv(env_var, value)
    assert determine_agent() == (True, CURSOR_CLI)


@pytest.mark.parametrize(
    ("env_var", "expected"),
    [
        ("ANTIGRAVITY_AGENT", ANTIGRAVITY),
        ("AUGMENT_AGENT", AUGMENT_CLI),
        ("OPENCODE_CLIENT", OPENCODE),
        ("REPL_ID", REPLIT),
    ],
)
def test_additional_agent_env_vars(monkeypatch, env_var, expected):
    """Newer agent-specific env vars should map to their canonical names."""
    monkeypatch.setenv(env_var, "1")
    assert determine_agent() == (True, expected)


def test_github_copilot_model(monkeypatch):
    """COPILOT_MODEL env var should detect GitHub Copilot."""
    monkeypatch.setenv("COPILOT_MODEL", "gpt-4")
    assert determine_agent() == (True, GITHUB_COPILOT)


def test_ai_agent_github_copilot_normalization(monkeypatch):
    """AI_AGENT=github-copilot-cli should normalize to github-copilot."""
    monkeypatch.setenv("AI_AGENT", "github-copilot-cli")
    assert determine_agent() == (True, GITHUB_COPILOT)


def test_devin_local_path(monkeypatch):
    """A Devin marker path should detect Devin when no env vars match."""
    monkeypatch.setattr(
        agents_module.os,
        "access",
        lambda path, mode: path == agents_module.DEVIN_LOCAL_PATH,
    )
    assert determine_agent() == (True, DEVIN)
