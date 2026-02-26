import inspect
import sys
import textwrap
from dataclasses import dataclass, field
from typing import Callable

import rich

from xclif.annotations import annotation2converter
from xclif.constants import INITIAL_LEFT_PADDING, NAME_DESC_PADDING, NO_DESC
from xclif.definition import IMPLICIT_OPTIONS, Argument, Option
from xclif.parser import parse_and_execute_impl


@dataclass
class Command:
    """A command that can be run."""

    name: str
    run: Callable[..., int]
    arguments: list[Argument] = field(default_factory=list)
    options: dict[str, Option] = field(default_factory=dict)
    subcommands: dict[str, "Command"] = field(default_factory=dict)
    # Implicit options live in a separate namespace so they are never
    # forwarded as kwargs to run(). Each Command gets its own copy so
    # individual commands can override or extend them in future.
    implicit_options: dict[str, Option] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.implicit_options:
            self.implicit_options = dict(IMPLICIT_OPTIONS)

    def print_short_help(self) -> None:
        all_options = {**self.implicit_options, **self.options}
        help_text = (
            (self.short_description + "\n" if self.short_description else "")
            + f"[b][u]Usage[/u]: {self.name}[/] [OPTIONS]"
            + (" " if self.arguments else "")
            + " ".join(f"[{x.name.upper()}]" for x in self.arguments)
            + "\n\n"
        )

        pad_length = max(
            *(len(x.name) for x in self.arguments),
            *map(len, self.subcommands),
            *(len(x) + 2 for x in all_options),
            0,
        )
        if self.subcommands:
            help_text += (
                "[b][u]Subcommands[/u]:[/]\n"
                + "\n".join(
                    " " * INITIAL_LEFT_PADDING
                    + f"[b]{name.ljust(pad_length + NAME_DESC_PADDING)}[/]"
                    + f"[i]{cmd.short_description}[/]"
                    for name, cmd in self.subcommands.items()
                )
                + "\n\n"
            )
        elif self.arguments:
            help_text += (
                "[b][u]Arguments[/u]:[/]\n"
                + "\n".join(
                    " " * INITIAL_LEFT_PADDING
                    + f"[b][{x.name}][/b]".ljust(pad_length + NAME_DESC_PADDING)
                    + f"[i]{x.description}[/]"
                    for x in self.arguments
                )
                + "\n\n"
            )
        # TODO: Aliases
        help_text += (
            "[b][u]Options[/u]:[/]\n"
            + "\n".join(
                "[b]"
                + " " * INITIAL_LEFT_PADDING
                + ("--" + name).ljust(pad_length + NAME_DESC_PADDING)
                + f"[/b][i]{opt.description}[/]"
                for name, opt in all_options.items()
            )
            + "\n\n"
        )
        rich.print(help_text)

    def print_long_help(self) -> None:
        all_options = {**self.implicit_options, **self.options}
        help_text = (
            (self.description + "\n" if self.short_description else "")
            + f"[b][u]Usage[/u]: {self.name}[/] [OPTIONS]"
            + (" " if self.arguments else "")
            + " ".join(f"[{x.name.upper()}]" for x in self.arguments)
            + "\n\n"
        )
        if self.subcommands:
            help_text += (
                "[b][u]Subcommands[/u]:[/]\n"
                + "\n".join(
                    f"{' ' * INITIAL_LEFT_PADDING}[b]{name}[/]{' ' * NAME_DESC_PADDING}[i]{cmd.short_description}[/]"
                    for name, cmd in self.subcommands.items()
                )
                + "\n\n"
            )
        elif self.arguments:
            help_text += (
                "[b][u]Arguments[/u]:[/]\n"
                + "\n".join(
                    f"[b]{' ' * INITIAL_LEFT_PADDING}[{x.name}][/]\n{textwrap.indent(x.description, '      ')}"
                    for x in self.arguments
                )
                + "\n\n"
            )
        # TODO: Aliases
        help_text += (
            "[b][u]Options[/u]:[/]\n"
            + "\n".join(
                f"{' ' * INITIAL_LEFT_PADDING}[b]--{name}[/]{' ' * NAME_DESC_PADDING}[i]{opt.description}[/]"
                for name, opt in all_options.items()
            )
            + "\n\n"
        )
        rich.print(help_text)

    def execute(self, args: list[str] | None = None) -> int:
        return parse_and_execute_impl(sys.argv[1:] if args is None else args, self)

    @property
    def description(self) -> str:
        return inspect.getdoc(self.run) or NO_DESC

    @property
    def short_description(self) -> str:
        return self.description.split("\n")[0]


def extract_parameters(function: Callable) -> tuple[list[Argument], dict[str, Option]]:
    # Use Python's type hints to extract arguments and options.
    # Positional-or-keyword params with no default → positional arguments.
    # Positional-or-keyword params with a default → --options.
    signature = inspect.signature(function, eval_str=True)
    arguments = []
    options = {}
    for name, parameter in signature.parameters.items():
        if parameter.kind != parameter.POSITIONAL_OR_KEYWORD:
            msg = "Positional-only, keyword-only, and variadic parameters are currently unsupported"
            raise TypeError(msg)
        if name in IMPLICIT_OPTIONS:
            msg = f"Cannot use `{name}` as an argument/option name (overrides an implicit option automatically created by Xclif)"
            raise ValueError(msg)
        if parameter.annotation is inspect.Parameter.empty:
            msg = f"Argument {name!r} has no type hint"
            raise ValueError(msg)
        converter = annotation2converter(parameter.annotation)
        if converter is None:
            msg = "Unsupported type"
            raise TypeError(msg)
        is_argument = parameter.default is inspect.Parameter.empty
        if is_argument:
            arguments.append(Argument(name, converter, NO_DESC))
        else:
            # TODO: Auto gen aliases
            options[name] = Option(name, converter, NO_DESC, parameter.default)
    return arguments, options


def command(name: None | str = None) -> Callable[[Callable], Command]:
    """Convert a function into an `xclif.Command`."""

    def _decorator(func: Callable) -> Command:
        if name is not None:
            command_name = name
        elif func.__name__ == "_":
            # Auto name from module
            command_name = func.__module__.split(".")[-1]
        else:
            command_name = func.__name__
        arguments, options = extract_parameters(func)
        return Command(command_name, func, arguments, options)

    return _decorator
