import inspect
import sys
import types
from dataclasses import dataclass
from typing import NoReturn, Self

from xclif.command import Command, command
from xclif.definition import Option
from xclif.importer import get_modules

__all__ = ["Cli", "WithConfig", "command"]


class WithConfig[T]:
    """Marker for parameters that can be read from a config file or env var.

    ``name: WithConfig[str]`` expresses intent — the parameter *should* fall back
    to a config file (TOML/JSON in the OS data dir) or an environment variable
    when not supplied on the CLI.  This is not yet implemented; the annotation
    is currently transparent (``WithConfig[str]`` behaves exactly like ``str``).

    Planned priority order: CLI flag > env var > config file > default.
    See: https://github.com/ThatXliner/xclif/issues/23
    """

    def __class_getitem__(cls, item: type) -> type:
        return item


def _detect_version(package_name: str) -> str | None:
    """Try to auto-detect the version from installed package metadata."""
    import importlib.metadata
    try:
        return importlib.metadata.version(package_name)
    except importlib.metadata.PackageNotFoundError:
        return None


@dataclass
class Cli:
    """The main API for Xclif."""

    root_command: Command
    version: str | None = None

    def __post_init__(self) -> None:
        from xclif.completions import make_completions_command

        # Add completions subcommand
        self.root_command.subcommands["completions"] = make_completions_command(
            self.root_command
        )

        # Inject --version as an implicit option on root command only
        self.root_command.implicit_options["version"] = Option(
            "version", bool, "Print program version and exit",
        )
        self.root_command.version = self.version

    def __call__(self) -> NoReturn:
        sys.exit(self.root_command.execute())

    def add_command(self, path: list[str], command: Command) -> None:
        cursor = self.root_command
        for part in path[:-1]:
            if cursor.arguments:
                msg = "Cannot add subcommands to a command with arguments"
                raise ValueError(msg)
            cursor = cursor.subcommands.setdefault(
                part, Command(part, lambda: 0)
            )
        cursor.subcommands[command.name] = command

    @classmethod
    def from_routes(cls, routes: types.ModuleType, *, version: str | None = None) -> Self:
        members = inspect.getmembers(routes, lambda x: isinstance(x, Command))

        if len(members) > 1:
            msg = f"Multiple commands found in root module ({routes.__name__!r})"
            raise ValueError(msg)
        elif len(members) == 0:
            msg = f"No commands found in root module ({routes.__name__!r})"
            raise ValueError(msg)
        if routes.__package__ is None:
            msg = f"Root module ({routes.__name__!r}) must be part of a package"
            raise ImportError(msg)

        # Auto-detect version if not explicitly provided
        if version is None:
            package_name = routes.__package__.split(".")[0]
            version = _detect_version(package_name)

        root_path = routes.__package__ + "."
        root_command = members[0][1]
        if root_command.name is None:
            msg = "Root command must have a name (it will determine the program name)"
            raise ValueError(msg)
        output = cls(root_command=root_command, version=version)
        for path, module in get_modules(routes):
            members = inspect.getmembers(module, lambda x: isinstance(x, Command))
            if not members:
                continue
            if len(members) > 1:
                msg = f"Multiple commands found in {path!r}"
                raise ValueError(msg)
            _name, function = members[0]
            output.add_command(path.removeprefix(root_path).split("."), function)
        return output
