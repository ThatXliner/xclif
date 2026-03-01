from xclif import Cli
from xclif.command import Command

root = Command("xclif-greeter", lambda: None)
cli = Cli(root_command=root)

@root.command()
def greet(name: str, greeting: str = "Hello", count: int = 1) -> None:
    """Greet someone."""
    for _ in range(count):
        print(f"{greeting}, {name}!")

@root.command(["config", "set"])
def set(key: str, value: str) -> None:
    """Set a config value."""
    print(f"Set {key}={value}")

@root.command(["config", "get"])
def get_cmd(key: str) -> None:
    """Get a config value."""
    print(f"Get {key}")

if __name__ == "__main__":
    cli()
