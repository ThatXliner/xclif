import json
import os

from xclif import command

_CONFIG_PATH = os.path.expanduser("~/.config/greeter/config.json")


@command("get")
def _() -> None:
    """Print the current greeter config."""
    try:
        with open(_CONFIG_PATH) as f:
            cfg = json.load(f)
    except FileNotFoundError:
        print("No config file found. Use `greeter config set` to create one.")
        return
    except json.JSONDecodeError:
        print(f"Config file at {_CONFIG_PATH} is malformed.")
        return

    if not cfg:
        print("Config is empty.")
        return

    for key, value in cfg.items():
        print(f"{key}: {value!r}")
