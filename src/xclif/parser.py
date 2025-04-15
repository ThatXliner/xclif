# import shlex
from collections import defaultdict
from typing import TYPE_CHECKING, Callable

from xclif.definition import Argument, Option

if TYPE_CHECKING:
    from xclif.command import Command


def flatten_dict_values[T](d: dict[str, list[T]]) -> dict[str, T | list[T]]:
    return {k: v if len(v) > 1 else v[0] for k, v in d.items()}


# def parse_option(options: dict[str, Option], arg: str):
#     if arg.startswith("-"):
#         # TODO: Parse options
#         if arg == "--":
#             msg = "We have not implemented the -- thing yet"
#             raise NotImplementedError(msg)
#             # SECURITY: or shlex.join????
#             # parsed_arguments.append(" ".join(args[i + 1 :]))
#             # break
#         if arg.startswith("--"):
#             snake_case = arg.removeprefix("--").replace("-", "_")
#             return options[snake_case].converter(arg)
#         else:
#             # TODO: get alias
#             msg = "Short options are not implemented yet"
#             raise NotImplementedError(msg)
#     else:
#         # Error: unexpected argument
#         msg = f"Unexpected argument {arg}"
#         raise RuntimeError(msg)


def parse_options[T](options: dict[str, Option], args: list[str]) -> dict[str, list[T]]:
    parsed_options = defaultdict(list)
    i = 0  # instead of a for loop since we may have like options with n items
    while i < len(args):
        arg = args[i]
        if arg.startswith("-"):
            # TODO: Parse options
            if arg == "--":
                msg = "We have not implemented the -- thing yet"
                raise NotImplementedError(msg)
                # SECURITY: or shlex.join????
                # parsed_arguments.append(" ".join(args[i + 1 :]))
                break
            if arg.startswith("--"):
                snake_case = arg.removeprefix("--").replace("-", "_")
                parsed_options[snake_case].append(options[snake_case].converter(arg))
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
    arguments: list[Argument],
    options: dict[str, Option],
    run: Callable[..., int],
    subcommands: dict[str, "Command"],
) -> int:
    # Parsing CLI subcommands are really easy: it's recursive.
    # Dependency injection can be done very easily as well.

    # There are 2 different types of incantations:
    # 1. The command takes no arguments and no options
    # 2. The command has subcommands (cannot have arguments, options are "global" and
    #    are passed to the subcommand, unless configured otherwise)

    if not subcommands:
        # TODO: implement "--"
        parsed_arguments = [
            arg.converter(raw) for raw, arg in zip(args, arguments, strict=False)
        ]
        parsed_options = parse_options(options, args[len(arguments) :])
        # TODO: Handle default options
        return run(*parsed_arguments, **flatten_dict_values(parsed_options))
    # Case 2: Subcommands
    # Parse global options before subcommands
    parsed_options = defaultdict(list)
    # Copy+pasted from the function definition with a very minor change
    # can't think of a more elegant way to do it lol
    i = 0
    while i < len(args):
        arg = args[i]
        if arg.startswith("-"):
            # TODO: Parse options
            if arg == "--":
                msg = "We have not implemented the -- thing yet"
                raise NotImplementedError(msg)
                # SECURITY: or shlex.join????
                # parsed_arguments.append(" ".join(args[i + 1 :]))
                break
            if arg.startswith("--"):
                snake_case = arg.removeprefix("--").replace("-", "_")
                parsed_options[snake_case].append(options[snake_case].converter(arg))
            else:
                # TODO: get alias
                msg = "Short options are not implemented yet"
                raise NotImplementedError(msg)
        else:
            break  # Prob a subcommand
        i += 1
    else:
        # No subcommands detected
        return run(**flatten_dict_values(parsed_options))
    # TODO: Figure cascading options
    if args[i] in subcommands:
        return subcommands[args[i]].execute(args[i + 1 :])
    if subcommands:
        # Fuzzy match and raise error about unknown command
        raise RuntimeError("Unknown subcommand")
    raise RuntimeError("unexpected argument")
