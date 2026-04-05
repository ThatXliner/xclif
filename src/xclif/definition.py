from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from xclif import WithConfig


@dataclass
class Argument[T]:
    name: str
    converter: Callable[[Any], T]
    description: str
    variadic: bool = False
    config: WithConfig | None = None
    choices: list[str] | None = None

    @property
    def short_description(self) -> str:
        return self.description.splitlines()[0]


@dataclass
class Option[T]:
    name: str
    converter: Callable[[Any], T]
    description: str
    default: Any = None
    cascading: bool = False
    is_list: bool = False
    aliases: list[str] = field(default_factory=list)
    config: WithConfig | None = None
    choices: list[str] | None = None

    @property
    def short_description(self) -> str:
        return self.description.splitlines()[0]


# Implicit options are added to every command automatically.
# They live in a separate namespace from user-defined options so they are
# never forwarded as kwargs to command.run().
#
# NOTE: --version is NOT here — it is injected by Cli onto the root command only.
IMPLICIT_OPTIONS: dict[str, Option] = {
    "help": Option("help", bool, "Show this help message and exit", aliases=["-h"]),
    "verbose": Option("verbose", bool, "Increase log verbosity (repeatable up to 3 times)", cascading=True, aliases=["-v"]),
    "colors": Option("colors", str, "Control color output (always|never|auto)", cascading=True),
}
