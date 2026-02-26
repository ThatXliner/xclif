from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from xclif.definition import Option

if TYPE_CHECKING:
    from xclif.command import Command


def _parse_token_stream(
    options: dict[str, Option],
    subcommands: dict[str, "Command"],
    args: list[str],
) -> tuple[list[str], dict[str, list], int | None]:
    """Scan a token stream at a single command level.

    Tokens are consumed left to right. Options (--name) are recognised and
    collected regardless of their position relative to positional tokens
    (interspersed options are supported). Scanning stops as soon as a token
    is identified as a subcommand name — that token's index is returned so
    the caller can hand off the tail to the subcommand parser.

    Returns:
        positionals  - raw positional tokens collected in order
        parsed_opts  - dict[name, [value, ...]] for all options seen
        subcmd_index - index into `args` of the subcommand token, or None
    """
    positionals: list[str] = []
    parsed_opts: dict[str, list] = defaultdict(list)
    i = 0
    while i < len(args):
        token = args[i]

        if token == "--":
            # Everything after -- is positional (raw passthrough — planned)
            raise NotImplementedError("The -- separator is not yet implemented")

        if token.startswith("--"):
            name = token.removeprefix("--").replace("-", "_")
            try:
                option = options[name]
            except KeyError as err:
                msg = f"Unknown option {token!r}"
                raise RuntimeError(msg) from err
            if option.converter is bool:
                parsed_opts[name].append(True)
            else:
                if i + 1 >= len(args):
                    msg = f"Option {token!r} requires a value"
                    raise RuntimeError(msg)
                i += 1
                parsed_opts[name].append(option.converter(args[i]))

        elif token.startswith("-"):
            # TODO: short option aliases
            msg = "Short options are not yet implemented"
            raise NotImplementedError(msg)

        elif token in subcommands:
            # Subcommand name — stop scanning, hand off tail
            return positionals, parsed_opts, i

        else:
            positionals.append(token)

        i += 1

    return positionals, parsed_opts, None


def parse_and_execute_impl(
    args: list[str],
    command: "Command",
    context: dict | None = None,
) -> int:
    """Parse `args` in the context of `command` and execute.

    `context` carries cascading option values resolved by ancestor commands.
    It is never passed as kwargs to command.run() — it is a separate concern.
    """
    if context is None:
        context = {}

    # Merge all option namespaces for scanning: user options + implicit options.
    # We keep them logically separate (implicit_options vs options on Command)
    # but the scanner needs to see both so it knows the arity of every token.
    all_options = {**command.implicit_options, **command.options}

    positionals, parsed_opts, subcmd_index = _parse_token_stream(
        all_options, command.subcommands, args
    )

    # --- Act on implicit options first, before any dispatch ---

    # --help: print help and exit immediately
    if parsed_opts.get("help"):
        if subcmd_index is not None:
            # --help before a subcommand name: show help for the subcommand
            subcommand = command.subcommands[args[subcmd_index]]
            subcommand.print_long_help()
        else:
            command.print_long_help()
        return 0

    # --version: only meaningful at root; upper layers handle it (TODO)
    if parsed_opts.get("version"):
        # TODO: plumb version string from Cli down here
        raise NotImplementedError("--version is not yet implemented")

    # Build updated cascading context for children
    new_context = dict(context)
    for name, option in command.implicit_options.items():
        if option.cascading and name in parsed_opts:
            values = parsed_opts[name]
            # For bool cascading flags (e.g. --verbose), count occurrences
            if option.converter is bool:
                existing = new_context.get(name, 0)
                new_context[name] = existing + len(values)
            else:
                new_context[name] = values[-1]  # last wins

    # --- Dispatch ---

    if subcmd_index is not None:
        # A subcommand token was found — recurse into it
        subcommand = command.subcommands[args[subcmd_index]]
        return parse_and_execute_impl(args[subcmd_index + 1:], subcommand, new_context)

    if command.subcommands and not positionals and not _user_opts(parsed_opts, command):
        # Namespace command invoked with no subcommand and no user args:
        # default action is short help
        command.print_short_help()
        return 0

    if command.subcommands and positionals:
        # The first positional-looking token wasn't a known subcommand
        raise RuntimeError(f"Unknown subcommand {positionals[0]!r}")

    # Leaf command: assign positionals and call run()
    declared_args = command.arguments
    if len(positionals) < sum(1 for a in declared_args):
        missing = [a.name for a in declared_args[len(positionals):]]
        msg = f"Missing required argument(s): {', '.join(missing)}"
        raise RuntimeError(msg)

    converted_args = [
        arg.converter(raw) for raw, arg in zip(positionals, declared_args)
    ]

    # Only user-defined option values go to run()
    user_kwargs: dict = {}
    for name, option in command.options.items():
        if name in parsed_opts:
            values = parsed_opts[name]
            user_kwargs[name] = values if len(values) > 1 else values[0]
        elif option.default is not None:
            user_kwargs[name] = option.default

    return command.run(*converted_args, **user_kwargs) or 0


def _user_opts(parsed_opts: dict, command: "Command") -> bool:
    """Return True if any user-defined options were parsed."""
    return any(k in command.options for k in parsed_opts)
