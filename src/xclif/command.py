import inspect
import sys
import textwrap
from dataclasses import dataclass, field
from typing import Callable

__all__ = ["Command", "command"]

from xclif.annotations import annotation2converter, is_list_type, unwrap_param_metadata
from xclif.constants import INITIAL_LEFT_PADDING, NAME_DESC_PADDING, NO_DESC
from xclif.definition import IMPLICIT_OPTIONS, Argument, _DefinitionOption
from xclif.errors import UsageError
from xclif.parser import parse_and_execute_impl

_AGENT_HIDDEN_SUBCOMMANDS = {"completions", "mcp"}


def _rprint(*args, **kwargs) -> None:
    import rich

    rich.print(*args, **kwargs)


def _get_console(**kwargs) -> "Console":
    from rich.console import Console

    return Console(**kwargs)


def _help_console(*, force_rich: bool = False, force_plain: bool = False) -> "Console":
    """Return a Console configured for the requested help mode."""
    from rich.console import Console

    if force_plain:
        return Console(no_color=True, highlight=False, soft_wrap=True)
    if force_rich:
        return Console(force_terminal=True, soft_wrap=True)
    return Console(soft_wrap=True)


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
    options: dict[str, _DefinitionOption] = field(default_factory=dict)
    subcommands: dict[str, "Command"] = field(default_factory=dict)
    implicit_options: dict[str, _DefinitionOption] = field(default_factory=dict)
    version: str | None = None
    aliases: list[str] = field(default_factory=list)
    show_no_description: bool = True

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

    def _format_option_label(self, name: str, option: _DefinitionOption) -> str:
        """Format an option name with its aliases for display."""
        parts = [f"--{option.name.replace('_', '-')}"]
        parts.extend(option.aliases)
        return ", ".join(parts)

    def print_short_help(
        self, *, force_rich: bool = False, force_plain: bool = False
    ) -> None:
        """Print a compact one-screen help summary to stdout."""
        if not force_rich and not force_plain and not _get_console().is_terminal:
            self.print_agent_help()
            return
        from rich.markup import escape

        console = _help_console(force_rich=force_rich, force_plain=force_plain)
        all_options = {**self.implicit_options, **self.options}
        alias_suffix = (
            f" [dim]({', '.join(self.aliases)})[/dim]" if self.aliases else ""
        )
        desc_header = self.short_description
        if desc_header == NO_DESC and not self.show_no_description:
            desc_header = ""
        help_text = (
            (desc_header + "\n" if desc_header else "")
            + f"[bold]Usage:[/bold] [cyan]{self.name}[/cyan]{alias_suffix} [dim]{escape('[OPTIONS]')}[/dim]"
            + (" " if self.arguments else "")
            + " ".join(_arg_markup(x) for x in self.arguments)
            + "\n\n"
        )

        option_labels = {
            name: self._format_option_label(name, opt)
            for name, opt in all_options.items()
        }
        # Build subcommand labels: "name <arg1> <arg2>" for leaves with args
        subcmd_labels = {
            name: _subcmd_label(name, cmd)
            for name, cmd in self.subcommands.items()
            if name == cmd.name
        }
        pad_length = max(
            [
                *(len(_arg_label(x)) + 2 for x in self.arguments),
                *(len(label) for label in subcmd_labels.values()),
                *(len(label) for label in option_labels.values()),
                0,
            ]
        )
        if self.subcommands:
            help_text += (
                "[bold]Subcommands:[/bold]\n"
                + "\n".join(
                    " " * INITIAL_LEFT_PADDING
                    + f"[cyan]{name}[/cyan]"
                    + f"[dim]{escape(_subcmd_args_suffix(cmd)).ljust(pad_length + NAME_DESC_PADDING - len(name))}[/dim]"
                    + _dim_description(cmd.short_description, show_no_desc=self.show_no_description)
                    for name, cmd in self.subcommands.items()
                    if name == cmd.name  # skip alias entries
                )
                + "\n\n"
            )
        elif self.arguments:
            help_text += (
                "[bold]Arguments:[/bold]\n"
                + "\n".join(
                    " " * INITIAL_LEFT_PADDING
                    + f"[dim cyan]{_arg_section_label(x).ljust(pad_length + NAME_DESC_PADDING)}[/dim cyan]"
                    + _dim_description(x.description, show_no_desc=self.show_no_description)
                    for x in self.arguments
                )
                + "\n\n"
            )
        help_text += (
            "[bold]Options:[/bold]\n"
            + "\n".join(
                " " * INITIAL_LEFT_PADDING
                + f"[cyan]{option_labels[name].ljust(pad_length + NAME_DESC_PADDING)}[/cyan]"
                + _dim_description(opt.description, show_no_desc=self.show_no_description)
                for name, opt in all_options.items()
            )
            + "\n\n"
        )
        console.print(help_text)

    def print_long_help(
        self, *, force_rich: bool = False, force_plain: bool = False
    ) -> None:
        """Print the full help page (including the long description) to stdout."""
        if not force_rich and not force_plain and not _get_console().is_terminal:
            self.print_agent_help()
            return
        from rich.markdown import Markdown
        from rich.markup import escape

        console = _help_console(force_rich=force_rich, force_plain=force_plain)
        all_options = {**self.implicit_options, **self.options}

        # Render the description as Markdown for rich formatting
        if self.short_description and (self.show_no_description or self.description != NO_DESC):
            console.print(Markdown(self.description))
            console.print()

        alias_suffix = (
            f" [dim]({', '.join(self.aliases)})[/dim]" if self.aliases else ""
        )
        help_text = (
            f"[bold]Usage:[/bold] [cyan]{self.name}[/cyan]{alias_suffix} [dim]{escape('[OPTIONS]')}[/dim]"
            + (" " if self.arguments else "")
            + " ".join(_arg_markup(x) for x in self.arguments)
            + "\n\n"
        )

        option_labels = {
            name: self._format_option_label(name, opt)
            for name, opt in all_options.items()
        }
        subcmd_labels = {
            name: _subcmd_label(name, cmd)
            for name, cmd in self.subcommands.items()
            if name == cmd.name
        }
        pad_length = max(
            [
                *(len(_arg_label(x)) + 2 for x in self.arguments),
                *(len(label) for label in subcmd_labels.values()),
                *(len(label) for label in option_labels.values()),
                0,
            ]
        )
        if self.subcommands:
            help_text += (
                "[bold]Subcommands:[/bold]\n"
                + "\n".join(
                    " " * INITIAL_LEFT_PADDING
                    + f"[cyan]{name}[/cyan]"
                    + f"[dim]{escape(_subcmd_args_suffix(cmd)).ljust(pad_length + NAME_DESC_PADDING - len(name))}[/dim]"
                    + _dim_description(cmd.short_description, show_no_desc=self.show_no_description)
                    for name, cmd in self.subcommands.items()
                    if name == cmd.name  # skip alias entries
                )
                + "\n\n"
            )
        elif self.arguments:
            indent_width = INITIAL_LEFT_PADDING + pad_length + NAME_DESC_PADDING
            help_text += (
                "[bold]Arguments:[/bold]\n"
                + "\n".join(
                    " " * INITIAL_LEFT_PADDING
                    + f"[dim cyan]{_arg_section_label(x).ljust(pad_length + NAME_DESC_PADDING)}[/dim cyan]"
                    + _dim_description(
                        textwrap.indent(x.description, " " * indent_width).strip(),
                        show_no_desc=self.show_no_description,
                    )
                    for x in self.arguments
                )
                + "\n\n"
            )
        help_text += (
            "[bold]Options:[/bold]\n"
            + "\n".join(
                " " * INITIAL_LEFT_PADDING
                + f"[cyan]{option_labels[name].ljust(pad_length + NAME_DESC_PADDING)}[/cyan]"
                + _dim_description(opt.description, show_no_desc=self.show_no_description)
                for name, opt in all_options.items()
            )
            + "\n\n"
        )
        console.print(help_text)

    def print_agent_help(self) -> None:
        """Print a hyper-short, token-efficient help summary for LLM agents.

        Automatically used when stdout is not a TTY (e.g. piped to another
        process or called by an agent). Recursively flattens the entire command
        tree and filters out framework-owned implicit options and hidden
        subcommands like ``completions``.

        Example output::

            myapp: My application.

            greet NAME - Greet someone. Options: --template STR (default: 'Hello, {}!')
            config get - Print the current config.
            config set KEY VALUE - Set config values.
        """
        args = _format_agent_args(self)
        desc = self.short_description
        if desc == NO_DESC and not self.show_no_description:
            desc = ""
        header = f"{self.name}{args}" + (f": {desc}" if desc else "")
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

    def execute(
        self, args: list[str] | None = None, context: dict | None = None
    ) -> int:
        """Parse *args* and run the appropriate subcommand, returning an exit code.

        When *args* is ``None``, ``sys.argv[1:]`` is used. Pass an explicit
        list for testing without subprocess overhead::

            assert my_command.execute(["greet", "Alice"]) == 0
        """
        try:
            return parse_and_execute_impl(
                sys.argv[1:] if args is None else args, self, context
            )
        except UsageError as exc:
            _rprint(f"[bold red]Error:[/bold red] {exc}", file=sys.stderr)
            if exc.hint:
                _rprint(f"[dim]{exc.hint}[/dim]", file=sys.stderr)
            _rprint(f"\n\nFor more information, try [bold cyan]{self.name} --help[/bold cyan].", file=sys.stderr)
            return 2

    @property
    def description(self) -> str:
        """Full docstring of the command's ``run`` function, cleaned by ``inspect.getdoc``."""
        return inspect.getdoc(self.run) or NO_DESC

    @property
    def short_description(self) -> str:
        """First line of :attr:`description`, used in subcommand listings."""
        return self.description.split("\n")[0]


def _dim_description(desc: str, show_no_desc: bool = True) -> str:
    """Return Rich markup for a description, italicizing 'No description'."""
    if not show_no_desc and desc == NO_DESC:
        return ""
    if desc == NO_DESC:
        return f"[dim italic]{desc}[/dim italic]"
    return f"[dim]{desc}[/dim]"


def _subcmd_args_suffix(cmd: "Command") -> str:
    """Return argument placeholders for a leaf subcommand, e.g. ' <name> <file>'."""
    if cmd.subcommands or not cmd.arguments:
        return ""
    parts = []
    for arg in cmd.arguments:
        label = _arg_label(arg)
        suffix = "..." if arg.variadic else ""
        parts.append(f"<{label.lower()}{suffix}>")
    return " " + " ".join(parts)


def _subcmd_label(name: str, cmd: "Command") -> str:
    """Return full display label for a subcommand including arg placeholders."""
    return name + _subcmd_args_suffix(cmd)


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
            args = _format_agent_args(sub)
            sub_desc = sub.short_description
            if sub_desc == NO_DESC and not sub.show_no_description:
                sub_desc = ""
            line = f"{path}{args}" + (f" - {sub_desc}" if sub_desc else "")
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


def _format_agent_args(cmd: "Command") -> str:
    """Format positional arguments for agent help, e.g. ' NAME FILE...'."""
    if not cmd.arguments:
        return ""
    parts: list[str] = []
    for arg in cmd.arguments:
        label = arg.name.upper()
        if arg.variadic:
            label += "..."
        parts.append(label)
    return " " + " ".join(parts)


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


def extract_parameters(
    function: Callable,
) -> tuple[list[Argument], dict[str, _DefinitionOption]]:
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

        if parameter.kind in (
            parameter.VAR_KEYWORD,
            parameter.POSITIONAL_ONLY,
            parameter.KEYWORD_ONLY,
        ):
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
        inner_type, arg_meta, opt_meta, with_config = unwrap_param_metadata(
            raw_annotation
        )

        converter = annotation2converter(inner_type)
        if converter is None:
            msg = "Unsupported type"
            raise TypeError(msg)
        is_argument = parameter.default is inspect.Parameter.empty
        list_valued = is_list_type(inner_type)

        if is_argument:
            if opt_meta is not None:
                msg = (
                    f"Option() used on argument parameter '{name}' — use Arg() instead"
                )
                raise ValueError(msg)
            description = (
                arg_meta.description if arg_meta and arg_meta.description else NO_DESC
            )
            display_name = arg_meta.name if arg_meta and arg_meta.name else name
            arguments.append(
                Argument(
                    display_name,
                    converter,
                    description,
                    config=with_config,
                    choices=_get_choices(converter),
                )
            )
        else:
            if arg_meta is not None:
                msg = f"Arg() used on option parameter '{name}' — use Option() instead"
                raise ValueError(msg)
            default = parameter.default
            description = (
                opt_meta.description if opt_meta and opt_meta.description else NO_DESC
            )
            cli_name = opt_meta.name if opt_meta and opt_meta.name else name
            if cli_name.replace("-", "_") in IMPLICIT_OPTIONS:
                msg = f"Cannot use `{cli_name}` as an option name (overrides an implicit option automatically created by Xclif)"
                raise ValueError(msg)
            aliases = _auto_alias(cli_name, taken_aliases)
            options[name] = _DefinitionOption(
                cli_name,
                converter,
                description,
                default,
                is_list=list_valued,
                aliases=aliases,
                config=with_config,
                choices=_get_choices(converter),
            )
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
