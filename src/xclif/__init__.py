import inspect
import sys
import types
from dataclasses import dataclass
from typing import NoReturn, Self

from xclif.command import Command
from xclif.importer import get_modules


@dataclass
class Cli:
    """The main API for Xclif."""

    root_command: Command

    def __post_init__(self) -> None:
        def completion_func():
            return print("TODO: completions") or 0

        completion_func.__doc__ = "Install completions for your shell"
        self.add_command(["completions"], Command("completions", completion_func))

    def __call__(self) -> NoReturn:
        """This method exists so that you can just add app.__main__.cli to the entry_points in setup.py and it will work."""
        sys.exit(self.root_command.execute())

    def add_command(self, path: list[str], command: Command) -> None:
        cursor = self.root_command
        for part in path[:-1]:
            if cursor.arguments:
                # TODO: But what if they used `--`?
                # Well we don't have support for that yet
                msg = "Cannot add subcommands to a command with arguments"
                raise ValueError(msg)
            # I can't guarantee a certain order of "a.a" coming before "a.a.a"
            # so what I'm going to do for now is this
            cursor = cursor.subcommands.setdefault(
                part, Command(part, lambda self: self.print_short_help() or 0)
            )
        cursor.subcommands[command.name] = command

    @classmethod
    def from_routes(cls, routes: types.ModuleType) -> Self:
        members = inspect.getmembers(routes, lambda x: isinstance(x, Command))

        if len(members) > 1:
            msg = f"Multiple commands found in root module ({routes.__name__!r})"
            raise ValueError(
                msg,
            )
        elif len(members) == 0:
            msg = f"No commands found in root module ({routes.__name__!r})"
            raise ValueError(msg)
        if routes.__package__ is None:
            msg = f"Root module ({routes.__name__!r}) must be part of a package"
            raise ImportError(msg)
        root_path = routes.__package__ + "."
        root_command = members[0][1]
        if root_command.name is None:
            msg = "Root command must have a name (it will determine the program name)"
            raise ValueError(
                msg,
            )
        output = cls(root_command=root_command)
        for path, module in get_modules(routes):
            members = inspect.getmembers(module, lambda x: isinstance(x, Command))
            # Keep it so it's one command per module
            if not members:
                continue
            if len(members) > 1:
                msg = f"Multiple commands found in {path!r}"
                raise ValueError(msg)
            _name, function = members[0]
            output.add_command(path.removeprefix(root_path).split("."), function)
        # if root_command.arguments and root_command.subcommands:
        #     raise ValueError(
        #         "Commands cannot have arguments and subcommands at the same time."
        #     )
        return output
