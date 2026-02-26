from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


# TODO: get name of converter/type for help text
# TODO: figure variadic arguments
@dataclass
class Argument[T]:
    name: str
    converter: Callable[[Any], T]
    description: str

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

    @property
    def short_description(self) -> str:
        return self.description.splitlines()[0]


# Implicit options are added to every command automatically.
# They live in a separate namespace from user-defined options so they are
# never forwarded as kwargs to command.run().
#
# cascading=True means the parsed value is carried into child commands as
# context, even when those children don't declare the option themselves.
IMPLICIT_OPTIONS: dict[str, Option] = {
    "help": Option("help", bool, "Show this help message and exit", cascading=False),
    "verbose": Option("verbose", bool, "Increase log verbosity (repeatable)", cascading=True),
    "colors": Option("colors", str, "Control color output (always|never|auto)", cascading=True),
    "version": Option("version", bool, "Print program version and exit", cascading=False),
}
