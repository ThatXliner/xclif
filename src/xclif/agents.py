"""Agent detection for LLM-optimized output.

Detects when xclif commands are being run by AI coding agents
and returns agent-optimized help instead of human-formatted output.
"""

import os

DEVIN_LOCAL_PATH = "/opt/.devin"

CURSOR = "cursor"
CURSOR_CLI = "cursor-cli"
CLAUDE = "claude"
COWORK = "cowork"
DEVIN = "devin"
REPLIT = "replit"
GEMINI = "gemini"
CODEX = "codex"
ANTIGRAVITY = "antigravity"
AUGMENT_CLI = "augment-cli"
OPENCODE = "opencode"
GITHUB_COPILOT = "github-copilot"
GITHUB_COPILOT_CLI = "github-copilot-cli"
V0 = "v0"

KNOWN_AGENTS = {
    "CURSOR": CURSOR,
    "CURSOR_CLI": CURSOR_CLI,
    "CLAUDE": CLAUDE,
    "COWORK": COWORK,
    "DEVIN": DEVIN,
    "REPLIT": REPLIT,
    "GEMINI": GEMINI,
    "CODEX": CODEX,
    "ANTIGRAVITY": ANTIGRAVITY,
    "AUGMENT_CLI": AUGMENT_CLI,
    "OPENCODE": OPENCODE,
    "GITHUB_COPILOT": GITHUB_COPILOT,
    "V0": V0,
}


def determine_agent() -> tuple[bool, str | None]:
    """Detect if running under an AI coding agent.

    Returns:
        Tuple of (is_agent, agent_name). If not an agent, returns (False, None).
    """
    ai_agent = os.environ.get("AI_AGENT")
    if ai_agent:
        name = ai_agent.strip()
        if name:
            if name in (GITHUB_COPILOT, GITHUB_COPILOT_CLI):
                return True, GITHUB_COPILOT
            if name == V0:
                return True, V0
            return True, name

    if os.environ.get("CURSOR_TRACE_ID"):
        return True, CURSOR

    if os.environ.get("CURSOR_AGENT") or os.environ.get("CURSOR_EXTENSION_HOST_ROLE") == "agent-exec":
        return True, CURSOR_CLI

    if os.environ.get("GEMINI_CLI"):
        return True, GEMINI

    if os.environ.get("CODEX_SANDBOX") or os.environ.get("CODEX_CI") or os.environ.get("CODEX_THREAD_ID"):
        return True, CODEX

    if os.environ.get("ANTIGRAVITY_AGENT"):
        return True, ANTIGRAVITY

    if os.environ.get("AUGMENT_AGENT"):
        return True, AUGMENT_CLI

    if os.environ.get("OPENCODE_CLIENT"):
        return True, OPENCODE

    if os.environ.get("CLAUDECODE") or os.environ.get("CLAUDE_CODE"):
        if os.environ.get("CLAUDE_CODE_IS_COWORK"):
            return True, COWORK
        return True, CLAUDE

    if os.environ.get("REPL_ID"):
        return True, REPLIT

    if os.environ.get("COPILOT_MODEL") or os.environ.get("COPILOT_ALLOW_ALL") or os.environ.get("COPILOT_GITHUB_TOKEN"):
        return True, GITHUB_COPILOT

    if os.access(DEVIN_LOCAL_PATH, os.F_OK):
        return True, DEVIN

    return False, None


def is_agent() -> bool:
    """Return True if running under an AI coding agent."""
    return determine_agent()[0]
