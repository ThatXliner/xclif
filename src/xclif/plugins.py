"""Plugin discovery for third-party subcommands via entry points or PATH."""

from __future__ import annotations

import logging
import shutil
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from xclif.command import Command

log = logging.getLogger(__name__)

EP_GROUP = "xclif.subcommands"


def discover_subcommands() -> dict[str, Command]:
    """Discover third-party subcommands registered via the ``xclif.subcommands`` entry point group.

    Each entry point should resolve to an ``xclif.Command`` instance.
    The entry point name becomes the subcommand name.
    Failed loads and type mismatches are logged and skipped.
    """
    import importlib.metadata

    from xclif.command import Command

    commands: dict[str, Command] = {}
    eps = importlib.metadata.entry_points(group=EP_GROUP)

    for ep in eps:
        try:
            obj = ep.load()
        except Exception as exc:
            log.warning("Failed to load plugin %r: %s", ep.name, exc)
            continue

        if isinstance(obj, Command):
            if ep.name in commands:
                log.warning("Duplicate plugin %r skipped (already registered)", ep.name)
            else:
                commands[ep.name] = obj
        else:
            log.warning(
                "Plugin %r resolved to %r, expected an xclif.Command instance",
                ep.name,
                type(obj).__name__,
            )
    return commands


def find_path_plugin(root_name: str, command_name: str) -> str | None:
    """Find ``{root_name}-{command_name}`` executable in PATH (Git-style).

    Uses ``shutil.which`` for cross-platform executable resolution,
    handling ``PATHEXT`` on Windows automatically.  Returns ``None``
    when ``PATH`` is not set.
    """
    import os

    if "PATH" not in os.environ:
        return None
    return shutil.which(f"{root_name}-{command_name}")
