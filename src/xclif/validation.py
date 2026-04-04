"""Validation for WithConfig conflict detection."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from xclif.command import Command
    from xclif.definition import Argument, Option


def check_with_config_conflicts(root: "Command", env_prefix: str) -> None:
    """Walk the command tree and check for WithConfig conflicts.

    Raises ValueError with an actionable message if two parameters
    share the same config key or env var but have different types.

    Every WithConfig param is checked for both config key and env var conflicts.
    """
    config_key_map: dict[str, list[tuple[type, str, str]]] = {}
    env_var_map: dict[str, list[tuple[type, str, str]]] = {}

    _walk_commands(root, env_prefix, config_key_map, env_var_map)

    for key, entries in config_key_map.items():
        types_seen = {e[0] for e in entries}
        if len(types_seen) > 1:
            first = entries[0]
            second = next(e for e in entries if e[0] != first[0])
            raise ValueError(
                f"WithConfig conflict: config key '{key}' is used as "
                f"{_type_name(first[0])} (in '{first[1]}', param '{first[2]}') "
                f"and {_type_name(second[0])} (in '{second[1]}', param '{second[2]}').\n\n"
                f"To fix, give one a distinct key:\n"
                f"    {second[2]}: Annotated[{_type_name(second[0])}, "
                f"WithConfig(key=\"{second[1]}_{second[2]}\")]"
            )

    for var, entries in env_var_map.items():
        types_seen = {e[0] for e in entries}
        if len(types_seen) > 1:
            first = entries[0]
            second = next(e for e in entries if e[0] != first[0])
            raise ValueError(
                f"WithConfig conflict: env var '{var}' maps to "
                f"{_type_name(first[0])} (in '{first[1]}', param '{first[2]}') "
                f"and {_type_name(second[0])} (in '{second[1]}', param '{second[2]}').\n\n"
                f"To fix, give one a distinct env var:\n"
                f"    {second[2]}: Annotated[{_type_name(second[0])}, "
                f"WithConfig(env=\"{second[1].upper()}_{second[2].upper()}\")]"
            )


def _walk_commands(
    command: "Command",
    env_prefix: str,
    config_key_map: dict,
    env_var_map: dict,
) -> None:
    """Recursively collect WithConfig metadata from the command tree.

    Every WithConfig param is recorded in both config_key_map and env_var_map.
    """

    for param in (*command.arguments, *command.options.values()):
        if param.config is None:
            continue
        cfg = param.config

        entry = (param.converter, command.name, param.name)

        # Every WithConfig param resolves both a config key and an env var
        # at runtime, so check both for conflicts.
        config_key = cfg.key if cfg.key else param.name
        config_key_map.setdefault(config_key, []).append(entry)

        env_var = cfg.env if cfg.env else f"{env_prefix}_{param.name.upper()}"
        env_var_map.setdefault(env_var, []).append(entry)

    for sub in command.subcommands.values():
        _walk_commands(sub, env_prefix, config_key_map, env_var_map)


def _type_name(converter: type) -> str:
    return getattr(converter, "__name__", str(converter))
