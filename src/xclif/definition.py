from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

__all__ = ["Argument", "_DefinitionOption", "IMPLICIT_OPTIONS"]

if TYPE_CHECKING:
    from xclif import WithConfig


@dataclass
class Argument[T]:
    """A positional argument on a command.

    Created automatically from a function signature by the :func:`~xclif.command.command`
    decorator.  Use :class:`~xclif.Arg` inside ``Annotated`` to attach a
    description or display name.
    """

    name: str
    converter: Callable[[Any], T]
    description: str
    variadic: bool = False
    config: WithConfig | None = None
    choices: list[str] | None = None

    @property
    def short_description(self) -> str:
        """First line of *description*, used in compact help output."""
        return self.description.splitlines()[0]


@dataclass
class _DefinitionOption[T]:
    """A named CLI option (``--flag`` or ``--name value``) on a command.

    Created automatically from a function signature by the :func:`~xclif.command.command`
    decorator.  Use :class:`~xclif.Option` inside ``Annotated`` to attach a
    description or override the flag name.
    """

    name: str
    converter: Callable[[Any], T]
    description: str
    default: Any = None
    cascading: bool = False
    is_list: bool = False
    aliases: list[str] = field(default_factory=list)
    config: WithConfig | None = None
    choices: list[str] | None = None
    optional_value: str | None = None

    @property
    def short_description(self) -> str:
        """First line of *description*, used in compact help output."""
        return self.description.splitlines()[0]


# Implicit options are added to every command automatically.
# They live in a separate namespace from user-defined options so they are
# never forwarded as kwargs to command.run().
#
# NOTE: --version is NOT here — it is injected by Cli onto the root command only.
IMPLICIT_OPTIONS: dict[str, _DefinitionOption] = {
    "help": _DefinitionOption("help", str, "Show this help message and exit (=plain|rich|agent)", aliases=["-h"], optional_value="auto"),
    "verbose": _DefinitionOption("verbose", bool, "Increase log verbosity (repeatable up to 3 times)", cascading=True, aliases=["-v"]),
    "colors": _DefinitionOption("colors", str, "Control color output (always|never|auto)", cascading=True),
}
