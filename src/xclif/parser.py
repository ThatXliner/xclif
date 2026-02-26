# import shlex

from collections import defaultdict
from typing import TYPE_CHECKING, Callable

from xclif.definition import Argument, Option

if TYPE_CHECKING:
    from xclif.command import Command


def flatten_dict_values[T](d: dict[str, list[T]]) -> dict[str, T | list[T]]:
    return {k: v if len(v) > 1 else v[0] for k, v in d.items()}


type _ParsedOptions[T] = dict[str, list[T]]


def parse_options[T](options: dict[str, Option], args: list[str]) -> _ParsedOptions[T]:
    parsed_options = defaultdict(list)
    i = 0  # instead of a for loop since we may have like options with n items
    while i < len(args):
        arg = args[i]
        if arg.startswith("-"):
            if arg == "--":
                msg = "We have not implemented the -- thing yet"
                raise NotImplementedError(msg)
            if arg.startswith("--"):
                snake_case = arg.removeprefix("--").replace("-", "_")
                try:
                    option = options[snake_case]
                except KeyError as err:
                    msg = f"Unknown option {arg}"
                    raise RuntimeError(msg) from err
                if option.converter is bool:
                    parsed_options[snake_case].append(True)
                else:
                    if i + 1 >= len(args):
                        msg = f"Option {arg} requires a value"
                        raise RuntimeError(msg)
                    i += 1
                    parsed_options[snake_case].append(option.converter(args[i]))
            else:
                # TODO: get alias
                msg = "Short options are not implemented yet"
                raise NotImplementedError(msg)
        else:
            # Error: unexpected argument
            msg = f"Unexpected argument {arg}"
            raise RuntimeError(msg)
        i += 1
    return parsed_options


# TODO: Finish and refactor this to be recursive on the Command
# class lol. We still need to have a crisis over the `--` being a thing
def parse_and_execute_impl(
    args: list[str],
    command: "Command",
) -> int:
    # Parsing CLI subcommands are really easy: it's recursive.
    # Dependency injection can be done very easily as well.

    # There are 2 different types of incantations:
    # 1. The command takes no arguments and no options
    # 2. The command has subcommands (cannot have arguments, options are "global" and
    #    are passed to the subcommand, unless configured otherwise)
    arguments = command.arguments
    subcommands = command.subcommands
    options = command.options
    subcommands = command.subcommands

    if not subcommands:
        # TODO: implement "--"
        parsed_arguments = [
            arg.converter(raw) for raw, arg in zip(args, arguments, strict=False)
        ]
        parsed_options = parse_options(options, args[len(arguments) :])
        return with_implicit_options(command)(
            *parsed_arguments, **flatten_dict_values(parsed_options)
        )
    # Case 2: Subcommands
    # Parse global options before subcommands
    parsed_options = defaultdict(list)
    # Copy+pasted from the function definition with a very minor change
    # can't think of a more elegant way to do it lol
    i = 0
    while i < len(args):
        arg = args[i]
        if arg.startswith("-"):
            if arg == "--":
                msg = "We have not implemented the -- thing yet"
                raise NotImplementedError(msg)
            if arg.startswith("--"):
                snake_case = arg.removeprefix("--").replace("-", "_")
                try:
                    option = options[snake_case]
                except KeyError as err:
                    msg = f"Unknown option {arg}"
                    raise RuntimeError(msg) from err
                if option.converter is bool:
                    parsed_options[snake_case].append(True)
                else:
                    if i + 1 >= len(args):
                        msg = f"Option {arg} requires a value"
                        raise RuntimeError(msg)
                    i += 1
                    parsed_options[snake_case].append(option.converter(args[i]))
            else:
                # TODO: get alias
                msg = "Short options are not implemented yet"
                raise NotImplementedError(msg)
        else:
            break  # Prob a subcommand
        i += 1
    else:
        # No subcommands detected
        return with_implicit_options(command)(**flatten_dict_values(parsed_options))
    # TODO: Figure cascading options
    if args[i] in subcommands:
        return subcommands[args[i]].execute(args[i + 1 :])
    if subcommands:
        # Fuzzy match and raise error about unknown command
        raise RuntimeError("Unknown subcommand")
    raise RuntimeError("unexpected argument")


def with_implicit_options(command: "Command") -> Callable[..., int]:
    def wrapper(*args, **kwargs) -> int:
        if kwargs.get("help"):
            command.print_long_help()
            return 0
        if kwargs.get("h"):
            command.print_short_help()
            return 0
        return command.run(*args, **kwargs) or 0

    return wrapper
