import json
import os

from xclif import command

_CONFIG_PATH = os.path.expanduser("~/.config/greeter/config.json")


def _load_config() -> dict:
    try:
        with open(_CONFIG_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


@command()
def _(name: str = "", template: str = "") -> None:
    """Greet someone by name.

    NAME defaults to the value stored in config (via `config set`).
    TEMPLATE defaults to "Hello, {}!" or the value stored in config.
    """
    cfg = _load_config()
    resolved_name = name or cfg.get("name", "")
    resolved_template = template or cfg.get("template", "Hello, {}!")
    if not resolved_name:
        print("Error: please provide a name or set one with `greeter config set --name <name>`")
        return
    print(resolved_template.format(resolved_name))
