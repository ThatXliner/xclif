import inspect
import sys
import textwrap
from dataclasses import dataclass, field
from typing import Callable

from xclif.annotations import annotation2converter, is_list_type
from xclif.constants import INITIAL_LEFT_PADDING, NAME_DESC_PADDING, NO_DESC
from xclif.definition import IMPLICIT_OPTIONS, Argument, Option
from xclif.errors import UsageError
from xclif.parser import parse_and_execute_impl


def _rprint(*args, **kwargs) -> None:
    import rich
    rich.print(*args, **kwargs)


@dataclass
class Command:
    """A command that can be run."""

    name: str
    run: Callable[..., int]
    arguments: list[Argument] = field(default_factory=list)
    options: dict[str, Option] = field(default_factory=dict)
    subcommands: dict[str, "Command"] = field(default_factory=dict)
    implicit_options: dict[str, Option] = field(default_factory=dict)
    version: str | None = None

    def __post_init__(self) -> None:
        if not self.implicit_options:
            self.implicit_options = dict(IMPLICIT_OPTIONS)

    def _assert_no_arguments(self, *, adding: str) -> None:
        if self.arguments:
            raise ValueError(
                f"Cannot add subcommand {adding!r} to command {self.name!r}: "
                "commands with positional arguments cannot have subcommands"
            )

    def _format_option_label(self, name: str, option: Option) -> str:
        """Format an option name with its aliases for display."""
        parts = [f"--{name.replace('_', '-')}"]
        parts.extend(option.aliases)
        return ", ".join(parts)

    def print_short_help(self) -> None:
        all_options = {**self.implicit_options, **self.options}
        help_text = (
            (self.short_description + "\n" if self.short_description else "")
            + f"[b][u]Usage[/u]: {self.name}[/] [OPTIONS]"
            + (" " if self.arguments else "")
            + " ".join(
                f"[{x.name.upper()}{'...' if x.variadic else ''}]"
                for x in self.arguments
            )
            + "\n\n"
        )

        option_labels = {
            name: self._format_option_label(name, opt)
            for name, opt in all_options.items()
        }
        pad_length = max(
            [
                *(len(x.name) for x in self.arguments),
                *map(len, self.subcommands),
                *(len(label) for label in option_labels.values()),
                0,
            ]
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
                    + f"[b][{x.name}{'...' if x.variadic else ''}][/b]".ljust(
                        pad_length + NAME_DESC_PADDING
                    )
                    + f"[i]{x.description}[/]"
                    for x in self.arguments
                )
                + "\n\n"
            )
        help_text += (
            "[b][u]Options[/u]:[/]\n"
            + "\n".join(
                "[b]"
                + " " * INITIAL_LEFT_PADDING
                + option_labels[name].ljust(pad_length + NAME_DESC_PADDING)
                + f"[/b][i]{opt.description}[/]"
                for name, opt in all_options.items()
            )
            + "\n\n"
        )
        _rprint(help_text)

    def print_long_help(self) -> None:
        all_options = {**self.implicit_options, **self.options}
        help_text = (
            (self.description + "\n" if self.short_description else "")
            + f"[b][u]Usage[/u]: {self.name}[/] [OPTIONS]"
            + (" " if self.arguments else "")
            + " ".join(
                f"[{x.name.upper()}{'...' if x.variadic else ''}]"
                for x in self.arguments
            )
            + "\n\n"
        )

        option_labels = {
            name: self._format_option_label(name, opt)
            for name, opt in all_options.items()
        }
        pad_length = max(
            [
                *(len(x.name) for x in self.arguments),
                *map(len, self.subcommands),
                *(len(label) for label in option_labels.values()),
                0,
            ]
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
            indent_width = INITIAL_LEFT_PADDING + pad_length + NAME_DESC_PADDING
            help_text += (
                "[b][u]Arguments[/u]:[/]\n"
                + "\n".join(
                    " " * INITIAL_LEFT_PADDING
                    + f"[b][{x.name}{'...' if x.variadic else ''}][/b]".ljust(
                        pad_length + NAME_DESC_PADDING
                    )
                    + textwrap.indent(x.description, " " * indent_width).strip()
                    for x in self.arguments
                )
                + "\n\n"
            )
        help_text += (
            "[b][u]Options[/u]:[/]\n"
            + "\n".join(
                "[b]"
                + " " * INITIAL_LEFT_PADDING
                + option_labels[name].ljust(pad_length + NAME_DESC_PADDING)
                + f"[/b][i]{opt.description}[/]"
                for name, opt in all_options.items()
            )
            + "\n\n"
        )
        _rprint(help_text)

    def command(self, name: str | None = None) -> "Callable[[Callable], Command]":
        def _decorator(func: Callable) -> "Command":
            cmd = command(name)(func)
            self._assert_no_arguments(adding=cmd.name)
            self.subcommands[cmd.name] = cmd
            return cmd
        return _decorator

    def execute(self, args: list[str] | None = None) -> int:
        try:
            return parse_and_execute_impl(sys.argv[1:] if args is None else args, self)
        except UsageError as exc:
            _rprint(f"[bold red]Error:[/bold red] {exc}", file=sys.stderr)
            if exc.hint:
                _rprint(f"[dim]{exc.hint}[/dim]", file=sys.stderr)
            return 2

    @property
    def description(self) -> str:
        return inspect.getdoc(self.run) or NO_DESC

    @property
    def short_description(self) -> str:
        return self.description.split("\n")[0]


def _auto_alias(name: str, taken: set[str]) -> list[str]:
    """Try to auto-generate a single-char short alias for an option name."""
    for char in name:
        alias = f"-{char}"
        if alias not in taken:
            taken.add(alias)
            return [alias]
    return []


def extract_parameters(function: Callable) -> tuple[list[Argument], dict[str, Option]]:
    """Extract arguments and options from a function's signature."""
    signature = inspect.signature(function, eval_str=True)
    arguments = []
    options = {}
    # Track taken aliases (implicit options reserve theirs)
    taken_aliases: set[str] = set()
    for opt in IMPLICIT_OPTIONS.values():
        taken_aliases.update(opt.aliases)

    for name, parameter in signature.parameters.items():
        if parameter.kind == parameter.VAR_POSITIONAL:
            # *args → variadic positional argument
            if parameter.annotation is inspect.Parameter.empty:
                msg = f"Variadic argument {name!r} has no type hint"
                raise ValueError(msg)
            converter = annotation2converter(parameter.annotation)
            if converter is None:
                msg = "Unsupported type"
                raise TypeError(msg)
            arguments.append(Argument(name, converter, NO_DESC, variadic=True))
            continue

        if parameter.kind in (parameter.VAR_KEYWORD, parameter.POSITIONAL_ONLY, parameter.KEYWORD_ONLY):
            msg = f"{'**kwargs' if parameter.kind == parameter.VAR_KEYWORD else 'Positional-only and keyword-only'} parameters are currently unsupported"
            raise TypeError(msg)

        if parameter.kind != parameter.POSITIONAL_OR_KEYWORD:
            msg = "Unsupported parameter kind"
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
        list_valued = is_list_type(parameter.annotation)
        if is_argument:
            arguments.append(Argument(name, converter, NO_DESC))
        else:
            default = parameter.default
            aliases = _auto_alias(name, taken_aliases)
            options[name] = Option(name, converter, NO_DESC, default, is_list=list_valued, aliases=aliases)
    return arguments, options


def command(name: None | str = None) -> Callable[[Callable], Command]:
    """Convert a function into an `xclif.Command`."""

    def _decorator(func: Callable) -> Command:
        if name is not None:
            command_name = name
        elif func.__name__ == "_":
            command_name = func.__module__.split(".")[-1]
        else:
            command_name = func.__name__
        arguments, options = extract_parameters(func)
        return Command(command_name, func, arguments, options)

    return _decorator
