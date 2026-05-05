"""Plugin discovery for third-party subcommands via entry points or PATH."""

from __future__ import annotations

import logging
import os
import stat
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
    try:
        eps = importlib.metadata.entry_points(group=EP_GROUP)
    except TypeError:
        # entry_points(group=...) may raise TypeError on older Python builds
        # or in environments where the importlib.metadata API is unavailable.
        return commands

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


def discover_path_subcommands(root_name: str) -> dict[str, Command]:
    """Discover executables named ``{root_name}-*`` in PATH (Git-style plugins).

    Scans each directory in PATH for executables matching ``{root_name}-<name>``.
    Returns Command objects tagged with ``_path_plugin_exe`` so the parser
    can short-circuit to a subprocess call.
    """
    prefix = f"{root_name}-"

    from xclif.command import Command

    commands: dict[str, Command] = {}
    seen_names: set[str] = set()

    for dir_path in os.environ.get("PATH", "").split(os.pathsep):
        if not dir_path:
            continue
        try:
            entries = os.listdir(dir_path)
        except (PermissionError, FileNotFoundError):
            continue

        for entry in entries:
            if not entry.startswith(prefix):
                continue
            name = entry.removeprefix(prefix)
            if not name or name in seen_names:
                continue

            full_path = os.path.join(dir_path, entry)
            try:
                st = os.stat(full_path)
            except OSError:
                continue
            is_exec = stat.S_ISREG(st.st_mode) and bool(st.st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))
            if not is_exec:
                continue

            cmd = Command(name, lambda: 0)
            cmd._path_plugin_exe = full_path
            commands[name] = cmd
            seen_names.add(name)

    return commands
