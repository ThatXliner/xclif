import inspect
import sys
import textwrap
from dataclasses import dataclass, field
from typing import Callable

__all__ = ["Command", "command"]

from xclif.annotations import annotation2converter, is_list_type, unwrap_param_metadata
from xclif.constants import INITIAL_LEFT_PADDING, NAME_DESC_PADDING, NO_DESC
from xclif.definition import IMPLICIT_OPTIONS, Argument, Option
from xclif.errors import UsageError
from xclif.parser import parse_and_execute_impl

_AGENT_HIDDEN_SUBCOMMANDS = {"completions"}


def _rprint(*args, **kwargs) -> None:
    import rich
    rich.print(*args, **kwargs)


def _get_console(**kwargs) -> "Console":
    from rich.console import Console
    return Console(**kwargs)


@dataclass
class Command:
    """A parsed command node in the CLI tree.

    Normally you don't construct this directly — use the :func:`command`
    decorator or :meth:`Command.command` / :meth:`Command.group` for the flat
    API.  The file-based routing approach (``Cli.from_routes``) builds the tree
    automatically from the package layout.
    """

    name: str
    run: Callable[..., int]
    arguments: list[Argument] = field(default_factory=list)
    options: dict[str, Option] = field(default_factory=dict)
    subcommands: dict[str, "Command"] = field(default_factory=dict)
    implicit_options: dict[str, Option] = field(default_factory=dict)
    version: str | None = None
    aliases: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.implicit_options:
            self.implicit_options = dict(IMPLICIT_OPTIONS)

    def _assert_no_arguments(self, *, adding: str) -> None:
        if self.arguments:
            raise ValueError(
                f"Cannot add subcommand {adding!r} to command {self.name!r}: "
                "commands with positional arguments cannot have subcommands"
            )

    def _assert_no_collision(self, name: str, *, registering: str) -> None:
        if name in self.subcommands:
            existing = self.subcommands[name]
            raise ValueError(
                f"Cannot register {registering!r} with name {name!r} on "
                f"command {self.name!r}: conflicts with existing "
                f"subcommand {existing.name!r}"
            )

    def _format_option_label(self, name: str, option: Option) -> str:
        """Format an option name with its aliases for display."""
        parts = [f"--{option.name.replace('_', '-')}"]
        parts.extend(option.aliases)
        return ", ".join(parts)

    def print_short_help(self) -> None:
        """Print a compact one-screen help summary to stdout."""
        all_options = {**self.implicit_options, **self.options}
        alias_suffix = f" [dim i]({', '.join(self.aliases)})[/dim i]" if self.aliases else ""
        help_text = (
            (self.short_description + "\n" if self.short_description else "")
            + f"[b][u]Usage[/u]: {self.name}[/]{alias_suffix} [OPTIONS]"
            + (" " if self.arguments else "")
            + " ".join(
                _arg_markup(x)
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
                *(len(_arg_label(x)) + 2 for x in self.arguments),
                *(len(cmd.name) for cmd in self.subcommands.values()),
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
                    if name == cmd.name  # skip alias entries
                )
                + "\n\n"
            )
        elif self.arguments:
            help_text += (
                "[b][u]Arguments[/u]:[/]\n"
                + "\n".join(
                    " " * INITIAL_LEFT_PADDING
                    + f"[b]{_arg_section_label(x).ljust(pad_length + NAME_DESC_PADDING)}[/b]"
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
        """Print the full help page (including the long description) to stdout."""
        from rich.markdown import Markdown

        all_options = {**self.implicit_options, **self.options}

        # Render the description as Markdown for rich formatting
        if self.short_description:
            console = _get_console()
            console.print(Markdown(self.description))
            console.print()

        alias_suffix = f" [dim i]({', '.join(self.aliases)})[/dim i]" if self.aliases else ""
        help_text = (
            f"[b][u]Usage[/u]: {self.name}[/]{alias_suffix} [OPTIONS]"
            + (" " if self.arguments else "")
            + " ".join(
                _arg_markup(x)
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
                *(len(_arg_label(x)) + 2 for x in self.arguments),
                *(len(cmd.name) for cmd in self.subcommands.values()),
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
                    if name == cmd.name  # skip alias entries
                )
                + "\n\n"
            )
        elif self.arguments:
            indent_width = INITIAL_LEFT_PADDING + pad_length + NAME_DESC_PADDING
            help_text += (
                "[b][u]Arguments[/u]:[/]\n"
                + "\n".join(
                    " " * INITIAL_LEFT_PADDING
                    + f"[b]{_arg_section_label(x).ljust(pad_length + NAME_DESC_PADDING)}[/b]"
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

    def print_agent_help(self) -> None:
        """Print a hyper-short, token-efficient help summary for LLM agents.

        Recursively flattens the entire command tree. Filters out framework-owned
        implicit options and hidden subcommands like ``completions``.
        """
        header = f"{self.name}: {self.short_description}"
        if not self.subcommands:
            # Leaf command: append own options to the header line
            opts = _format_agent_options(self)
            if opts:
                header += f" Options: {opts}"
        print(header)
        lines = _collect_agent_lines(self, prefix="")
        if lines:
            print()
            print("\n".join(lines))

    def command(self, *names: str) -> "Callable[[Callable], Command]":
        """Register a subcommand on this command using the decorator API.

        This is the flat API alternative to file-based routing. For large
        codebases where better scaling is desirable, consider the manifest
        compiler (``xclif compile``) instead, which pre-builds a static
        manifest and avoids the filesystem walk cost of ``Cli.from_routes``.
        """
        def _decorator(func: Callable) -> "Command":
            cmd = command(*names)(func)
            self._assert_no_arguments(adding=cmd.name)
            self._assert_no_collision(cmd.name, registering=cmd.name)
            self.subcommands[cmd.name] = cmd
            for alias in cmd.aliases:
                self._assert_no_collision(alias, registering=cmd.name)
                self.subcommands[alias] = cmd
            return cmd
        return _decorator

    def group(self, name: str) -> "Command":
        """Create an empty subcommand group on this command.

        Part of the flat decorator API. For large codebases where better
        scaling is desirable, consider the manifest compiler
        (``xclif compile``) to pre-build a static manifest instead.
        """
        self._assert_no_arguments(adding=name)
        cmd = Command(name, lambda: 0)
        self.subcommands[name] = cmd
        return cmd

    def execute(self, args: list[str] | None = None, context: dict | None = None) -> int:
        """Parse *args* and run the appropriate subcommand, returning an exit code.

        When *args* is ``None``, ``sys.argv[1:]`` is used. Pass an explicit
        list for testing without subprocess overhead::

            assert my_command.execute(["greet", "Alice"]) == 0
        """
        try:
            return parse_and_execute_impl(sys.argv[1:] if args is None else args, self, context)
        except UsageError as exc:
            _rprint(f"[bold red]Error:[/bold red] {exc}", file=sys.stderr)
            if exc.hint:
                _rprint(f"[dim]{exc.hint}[/dim]", file=sys.stderr)
            return 2

    @property
    def description(self) -> str:
        """Full docstring of the command's ``run`` function, cleaned by ``inspect.getdoc``."""
        return inspect.getdoc(self.run) or NO_DESC

    @property
    def short_description(self) -> str:
        """First line of :attr:`description`, used in subcommand listings."""
        return self.description.split("\n")[0]


def _arg_label(arg: "Argument") -> str:
    """Return the inner label for an argument (no brackets), e.g. 'bash|zsh|fish' or 'NAME'."""
    if arg.choices:
        return "|".join(arg.choices)
    return arg.name.upper() if not arg.variadic else arg.name.upper()


def _arg_markup(arg: "Argument") -> str:
    """Return a Rich-safe bracketed label for an argument, e.g. '[bash|zsh|fish]' or '[NAME]'."""
    from rich.markup import escape
    inner = _arg_label(arg)
    suffix = "..." if arg.variadic else ""
    return escape(f"[{inner}{suffix}]")


def _arg_section_label(arg: "Argument") -> str:
    """Return a Rich-safe label for the Arguments section listing, e.g. '[bash|zsh|fish]' or '[name]'."""
    from rich.markup import escape
    inner = "|".join(arg.choices) if arg.choices else arg.name
    suffix = "..." if arg.variadic else ""
    return escape(f"[{inner}{suffix}]")


def _collect_agent_lines(cmd: "Command", prefix: str) -> list[str]:
    """Recursively collect flattened command lines for agent help."""
    lines: list[str] = []
    seen_ids: set[int] = set()
    for name, sub in cmd.subcommands.items():
        if id(sub) in seen_ids:  # skip alias entries (same object under multiple keys)
            continue
        seen_ids.add(id(sub))
        if name in _AGENT_HIDDEN_SUBCOMMANDS:
            continue
        path = f"{prefix}{name}" if prefix else name
        if sub.subcommands:
            # Non-leaf: recurse, don't emit a line for the group itself
            lines.extend(_collect_agent_lines(sub, path + " "))
        else:
            # Leaf command
            line = f"{path} - {sub.short_description}"
            opts = _format_agent_options(sub)
            if opts:
                line += f" Options: {opts}"
            lines.append(line)
    return lines


def _format_agent_options(cmd: "Command") -> str:
    """Format user-defined options for agent help output."""
    parts: list[str] = []
    for name, opt in cmd.options.items():
        flag = f"--{opt.name.replace('_', '-')}"
        if opt.converter is bool:
            parts.append(flag)
        else:
            type_name = opt.converter.__name__.upper()
            part = f"{flag} {type_name}"
            if opt.default is not None and opt.default != "":
                part += f" (default: {opt.default!r})"
            parts.append(part)
    return ", ".join(parts)


def _get_choices(converter) -> list[str] | None:
    """Return choices list if converter is a Literal converter, else None."""
    return getattr(converter, "__choices__", None)


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
            inner_type, _, _, _ = unwrap_param_metadata(parameter.annotation)
            converter = annotation2converter(inner_type)
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

        # Unwrap all Annotated metadata: Arg, Option (annotation), WithConfig
        raw_annotation = parameter.annotation
        inner_type, arg_meta, opt_meta, with_config = unwrap_param_metadata(raw_annotation)

        converter = annotation2converter(inner_type)
        if converter is None:
            msg = "Unsupported type"
            raise TypeError(msg)
        is_argument = parameter.default is inspect.Parameter.empty
        list_valued = is_list_type(inner_type)

        if is_argument:
            if opt_meta is not None:
                msg = f"Option() used on argument parameter '{name}' — use Arg() instead"
                raise ValueError(msg)
            description = arg_meta.description if arg_meta and arg_meta.description else NO_DESC
            display_name = arg_meta.name if arg_meta and arg_meta.name else name
            arguments.append(Argument(display_name, converter, description, config=with_config, choices=_get_choices(converter)))
        else:
            if arg_meta is not None:
                msg = f"Arg() used on option parameter '{name}' — use Option() instead"
                raise ValueError(msg)
            default = parameter.default
            description = opt_meta.description if opt_meta and opt_meta.description else NO_DESC
            cli_name = opt_meta.name if opt_meta and opt_meta.name else name
            aliases = _auto_alias(cli_name, taken_aliases)
            options[name] = Option(cli_name, converter, description, default, is_list=list_valued, aliases=aliases, config=with_config, choices=_get_choices(converter))
    return arguments, options


def command(*names: str) -> Callable[[Callable], Command]:
    """Convert a function into an `xclif.Command`.

    Names are optional. The first name is the canonical command name; any
    additional names become aliases (alternative names that resolve to the
    same command). When no names are given, the function name is used
    (or the module name when the function is called ``_``).
    """

    def _decorator(func: Callable) -> Command:
        if names:
            command_name = names[0]
            aliases = list(names[1:])
        elif func.__name__ == "_":
            command_name = func.__module__.split(".")[-1]
            aliases = []
        else:
            command_name = func.__name__
            aliases = []
        arguments, options = extract_parameters(func)
        return Command(command_name, func, arguments, options, aliases=aliases)

    return _decorator
