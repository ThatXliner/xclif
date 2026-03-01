from xclif import Cli
from xclif.command import Command, command

root = Command("xclif-greeter", lambda: None)
cli = Cli(root_command=root)

@root.command()
def greet(name: str, greeting: str = "Hello", count: int = 1) -> None:
    """Greet someone."""
    for _ in range(count):
        print(f"{greeting}, {name}!")

@command()
def set(key: str, value: str) -> None:
    """Set a config value."""
    print(f"Set {key}={value}")

@command("get")
def get_cmd(key: str) -> None:
    """Get a config value."""
    print(f"Get {key}")

cli.add_command(["config", "set"], set)
cli.add_command(["config", "get"], get_cmd)

if __name__ == "__main__":
    cli()
