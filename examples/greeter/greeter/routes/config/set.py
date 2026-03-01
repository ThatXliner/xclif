import json
import os

from xclif import command

_CONFIG_PATH = os.path.expanduser("~/.config/greeter/config.json")


@command()
def _(name: str = "", template: str = "") -> None:
    """Set config values for the greeter.

    Persists NAME and/or TEMPLATE to ~/.config/greeter/config.json.
    """
    os.makedirs(os.path.dirname(_CONFIG_PATH), exist_ok=True)
    try:
        with open(_CONFIG_PATH) as f:
            cfg = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        cfg = {}

    if name:
        cfg["name"] = name
    if template:
        cfg["template"] = template

    with open(_CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)

    print(f"Config saved to {_CONFIG_PATH}")
