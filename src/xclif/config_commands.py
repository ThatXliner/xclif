"""Auto-injected config subcommands for apps using WithConfig."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from xclif.command import Command


def _has_with_config(command: "Command") -> bool:
    """Return True if any param in the command tree uses WithConfig."""
    for param in (*command.arguments, *command.options.values()):
        if param.config is not None:
            return True
    return any(_has_with_config(sub) for sub in command.subcommands.values())


def _print_flat(data: dict, prefix: str = "") -> None:
    """Print a nested dict as flat key: value lines."""
    for k, v in data.items():
        full_key = f"{prefix}{k}" if not prefix else f"{prefix}.{k}"
        if isinstance(v, dict):
            _print_flat(v, full_key)
        else:
            print(f"{full_key}: {v!r}")


def _set_nested(data: dict, key: str, value: str) -> None:
    """Set a value in a nested dict using a dotted key."""
    parts = key.split(".")
    current = data
    for part in parts[:-1]:
        current = current.setdefault(part, {})
    current[parts[-1]] = value


def _set_nested_toml(doc, key: str, value: str) -> None:
    """Set a value in a tomlkit document using a dotted key."""
    import tomlkit

    parts = key.split(".")
    current = doc
    for part in parts[:-1]:
        if part not in current:
            current[part] = tomlkit.table()
        current = current[part]
    current[parts[-1]] = value


def make_config_command(config_dir: Path) -> "Command":
    """Build the config subcommand tree (get, set, path)."""
    from xclif.command import Command
    from xclif.config import load_config, resolve_key
    from xclif.definition import Argument

    def get_run(*keys: str) -> int:
        """Print config values. Optionally specify KEY(s) to show specific values."""
        data = load_config(config_dir)
        if not data and not keys:
            print("No config file found or config is empty.")
            return 0
        if keys:
            _MISSING = object()
            exit_code = 0
            for key in keys:
                value = resolve_key(data, key, _MISSING)
                if value is _MISSING:
                    print(f"Key {key!r} not found in config.")
                    exit_code = 1
                else:
                    print(f"{key}: {value!r}")
            return exit_code
        _print_flat(data)
        return 0

    def set_run(key: str, value: str) -> int:
        """Set a config value. Creates a TOML config file if none exists."""
        toml_path = config_dir / "config.toml"
        json_path = config_dir / "config.json"

        if json_path.is_file() and not toml_path.is_file():
            data = json.loads(json_path.read_text(encoding="utf-8"))
            _set_nested(data, key, value)
            config_dir.mkdir(parents=True, exist_ok=True)
            json_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        else:
            import tomlkit

            if toml_path.is_file():
                doc = tomlkit.loads(toml_path.read_text(encoding="utf-8"))
            else:
                doc = tomlkit.document()
            _set_nested_toml(doc, key, value)
            config_dir.mkdir(parents=True, exist_ok=True)
            toml_path.write_text(tomlkit.dumps(doc), encoding="utf-8")

        print(f"Set {key!r} = {value!r}")
        return 0

    def path_run() -> int:
        """Print the config file directory path."""
        print(str(config_dir))
        return 0

    config = Command(
        "config",
        lambda: 0,
        subcommands={
            "get": Command("get", get_run, arguments=[
                Argument("keys", str, "Config key(s) to read", variadic=True),
            ]),
            "set": Command("set", set_run, arguments=[
                Argument("key", str, "Config key to set"),
                Argument("value", str, "Value to set"),
            ]),
            "path": Command("path", path_run),
        },
    )
    return config
