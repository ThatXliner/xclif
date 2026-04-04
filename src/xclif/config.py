"""Config file loading and key resolution for WithConfig parameters."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_MISSING = object()


def load_config(config_dir: Path) -> dict[str, Any]:
    """Load config from a directory, preferring TOML over JSON.

    Returns an empty dict if no config file is found.
    """
    toml_path = config_dir / "config.toml"
    if toml_path.is_file():
        import tomlkit
        return dict(tomlkit.loads(toml_path.read_text(encoding="utf-8")))

    json_path = config_dir / "config.json"
    if json_path.is_file():
        return json.loads(json_path.read_text(encoding="utf-8"))

    return {}


def resolve_key(data: dict[str, Any], key: str, default: Any = _MISSING) -> Any:
    """Resolve a possibly-dotted key in a nested dict.

    ``resolve_key(d, "a.b.c")`` returns ``d["a"]["b"]["c"]``.
    Returns *default* if any segment is missing or a non-dict intermediate
    is encountered. Raises ``KeyError`` if missing and no default is given.
    """
    parts = key.split(".")
    current: Any = data
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            if default is _MISSING:
                raise KeyError(key)
            return default
        current = current[part]
    return current
