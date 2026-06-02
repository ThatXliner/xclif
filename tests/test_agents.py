"""Tests for agent detection."""

import pytest
from xclif.agents import determine_agent, is_agent, CLAUDE, CURSOR, GEMINI, CODEX, GITHUB_COPILOT, COWORK


def test_no_agent_by_default(monkeypatch):
    """Without agent env vars, should return False."""
    for var in ["AI_AGENT", "CURSOR_TRACE_ID", "GEMINI_CLI", "CLAUDECODE", "CLAUDE_CODE"]:
        monkeypatch.delenv(var, raising=False)
    assert determine_agent() == (False, None)
    assert is_agent() is False


def test_ai_agent_env_var(monkeypatch):
    """AI_AGENT env var should be detected."""
    monkeypatch.setenv("AI_AGENT", "custom-agent")
    assert determine_agent() == (True, "custom-agent")


def test_claude_code_env_var(monkeypatch):
    """CLAUDE_CODE env var should detect Claude."""
    for var in ["AI_AGENT", "CURSOR_TRACE_ID", "GEMINI_CLI"]:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("CLAUDE_CODE", "1")
    monkeypatch.delenv("CLAUDE_CODE_IS_COWORK", raising=False)
    assert determine_agent() == (True, CLAUDE)


def test_claude_code_cowork(monkeypatch):
    """CLAUDE_CODE with CLAUDE_CODE_IS_COWORK should detect Cowork."""
    for var in ["AI_AGENT", "CURSOR_TRACE_ID", "GEMINI_CLI"]:
        monkeypatch.delenv(var, raising=False)
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
    for var in ["AI_AGENT", "CURSOR_TRACE_ID"]:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("GEMINI_CLI", "1")
    assert determine_agent() == (True, GEMINI)


def test_codex_sandbox(monkeypatch):
    """CODEX_SANDBOX env var should detect Codex."""
    for var in ["AI_AGENT", "CURSOR_TRACE_ID", "GEMINI_CLI"]:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("CODEX_SANDBOX", "1")
    assert determine_agent() == (True, CODEX)


def test_github_copilot_model(monkeypatch):
    """COPILOT_MODEL env var should detect GitHub Copilot."""
    for var in ["AI_AGENT", "CURSOR_TRACE_ID", "GEMINI_CLI", "CLAUDECODE", "CLAUDE_CODE", "REPL_ID"]:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("COPILOT_MODEL", "gpt-4")
    assert determine_agent() == (True, GITHUB_COPILOT)


def test_ai_agent_github_copilot_normalization(monkeypatch):
    """AI_AGENT=github-copilot-cli should normalize to github-copilot."""
    monkeypatch.setenv("AI_AGENT", "github-copilot-cli")
    assert determine_agent() == (True, GITHUB_COPILOT)
