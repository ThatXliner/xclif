# TODO: Figure better API
import inspect
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from xclif.annotations import annotation2converter
    from xclif.command import Command
from xclif.constants import NO_DESC


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


# XXX: Inheritance of dataclasses? A parameter super class?
@dataclass
class Option[T]:
    name: str
    converter: Callable[[Any], T]
    description: str
    default: None | str = None  # XXX: may not be necessary

    @property
    def short_description(self) -> str:
        return self.description.splitlines()[0]


IMPLICIT_OPTIONS = {
    "help": Option("help", bool, "Show this help message and exit"),
    "verbose": Option("verbose", list, "Change verbosity levels"),
    "colors": Option("colors", str, "Control color output"),
    "version": Option("version", str, "Print program version"),
}


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
        # if empty:
        #     if arguments or options:
        #         msg = "Empty commands cannot have arguments or options"
        #         raise ValueError(msg)
        #     return NamespaceCommand(
        #         command_name,
        #         description=inspect.getdoc(func) or "",
        # )
        return Command(command_name, func, arguments, options)

    return _decorator


# TODO: Potential command overloading (and automatic
# argument mutually exclusiveness, etc, etc)
def extract_parameters(function: Callable) -> tuple[list[Argument], dict[str, Option]]:
    # Use Python's type hints to extract arguments
    # and options. We don't use get_annotations
    # because we also want information on the defaults
    # and whether or not it is keyword/positional only
    signature = inspect.signature(function, eval_str=True)
    # type_hints = get_type_hints(function)
    # type_hints_with_metadata = get_type_hints(function, include_extras=True)
    arguments = []
    options = {}
    # TODO: The specification of arguments and options
    # can be done in the function signature
    # because there's positional only, keyword only, etc
    for name, parameter in signature.parameters.items():
        if parameter.kind != parameter.POSITIONAL_OR_KEYWORD:
            msg = "Positional-only, keyword-only, and variadic parameters are currently unsupported"
            raise TypeError(
                msg,
            )
        if name in IMPLICIT_OPTIONS:
            msg = f"Cannot use `{name}` as an argument/option name (overrides an implicit option automatically created by Xclif)"
            raise ValueError(
                msg,
            )
        # metadata = ()
        if parameter.annotation is inspect.Parameter.empty:
            msg = f"Argument {name} has no type hint"
            raise ValueError(msg)
        # if type_hints[name] != type_hints_with_metadata[name]:
        #     metadata = type_hints_with_metadata[name].__metadata__
        #     annotation = type_hints[name]
        converter = annotation2converter(parameter.annotation)
        if converter is None:
            msg = "Unsupported type"
            raise TypeError(msg)
        is_argument = parameter.default is inspect.Parameter.empty
        # TODO: Get description based on annotation
        if is_argument:
            arguments.append(Argument(name, converter, NO_DESC))
        else:
            # TODO: Auto gen aliases
            options[name] = Option(name, converter, NO_DESC, parameter.default)
    return arguments, options
