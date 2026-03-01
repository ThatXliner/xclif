"""Xclif argument parser.

Parsing algorithm
=================

Xclif uses a **recursive-descent, single-pass** parser that walks the token
stream left to right. Parsing happens in two cooperating layers:

1. **Token scanning** (`_parse_token_stream`) — a single command level.
2. **Recursive dispatch** (`parse_and_execute_impl`) — the full command tree.

Token scanning
--------------

At each command level the scanner classifies every token::

    --name value    → long option (space form)
    --name=value    → long option (equals form)
    -x              → short alias (looked up in the alias map)
    --              → sentinel; everything after is a raw positional
    <subcommand>    → stops scanning; returns the index so the caller can recurse
    <anything else> → positional argument

Options and positionals may be **interspersed** — options are collected
regardless of their position relative to positional tokens. Boolean flags
consume no following token; value options greedily consume the next token
(even if it happens to match a subcommand name).

Recursive dispatch
------------------
`parse_and_execute_impl` is called once per command level:

1. Merge implicit options (--help, --verbose, etc.) with user-defined options.
2. Run `_parse_token_stream` to separate positionals, options, and detect a
   subcommand boundary.
3. Handle implicit options first (--help prints help and exits; --version
   prints version and exits).
4. Build the **cascading context** — implicit options marked ``cascading=True``
   propagate their values down the command tree.
5. **Dispatch:** recurse into the found subcommand, print short help if there
   are no subcommand/positionals/user-opts, or bind positionals to declared
   arguments and call ``command.run()``.

Error handling
--------------
All user-facing parse errors raise `UsageError`. When invoked via
`Command.execute`, these are caught, formatted with Rich, and printed to
stderr with exit code 2. Edit-distance suggestions are provided for unknown
options and subcommands.

List options
------------
Options annotated as ``list[T]`` (e.g. ``list[str]``) collect all
occurrences into a list. Repeated ``--tag a --tag b`` produces ``["a", "b"]``.
Single occurrences still produce a one-element list (never unwrapped).
"""
from __future__ import annotations

from collections import defaultdict
from difflib import get_close_matches
from typing import TYPE_CHECKING

from xclif.definition import Option
from xclif.errors import UsageError

if TYPE_CHECKING:
    from xclif.command import Command


def _build_alias_map(options: dict[str, Option]) -> dict[str, str]:
    """Build a mapping from short alias → long option name."""
    alias_map: dict[str, str] = {}
    for long_name, option in options.items():
        for alias in option.aliases:
            alias_map[alias] = long_name
    return alias_map


def _type_name(converter: type) -> str:
    """Return a human-readable name for a type converter."""
    return getattr(converter, "__name__", str(converter))


def _suggest_option(name: str, options: dict[str, Option]) -> str | None:
    """Suggest a close match for an unknown option name."""
    candidates = [f"--{n.replace('_', '-')}" for n in options]
    matches = get_close_matches(name, candidates, n=1, cutoff=0.6)
    return matches[0] if matches else None


def _parse_token_stream(
    options: dict[str, Option],
    subcommands: dict[str, "Command"],
    args: list[str],
) -> tuple[list[str], dict[str, list], int | None]:
    """Scan a token stream at a single command level.

    Tokens are consumed left to right. Options (--name / -x) are recognised
    and collected regardless of their position relative to positional tokens
    (interspersed options are supported). Scanning stops as soon as a token
    is identified as a subcommand name — that token's index is returned so
    the caller can hand off the tail to the subcommand parser.

    Returns:
        positionals  - raw positional tokens collected in order
        parsed_opts  - dict[name, [value, ...]] for all options seen
        subcmd_index - index into `args` of the subcommand token, or None
    """
    alias_map = _build_alias_map(options)
    positionals: list[str] = []
    parsed_opts: dict[str, list] = defaultdict(list)
    i = 0
    while i < len(args):
        token = args[i]

        if token == "--":
            # Everything after -- is a raw positional
            positionals.extend(args[i + 1 :])
            break

        if token.startswith("--"):
            # Long option: --name value  or  --name=value
            if "=" in token:
                name_part, value = token.split("=", 1)
                name = name_part.removeprefix("--").replace("-", "_")
                if name not in options:
                    suggestion = _suggest_option(name_part, options)
                    hint = f"Did you mean '{suggestion}'?" if suggestion else None
                    raise UsageError(f"Unknown option {name_part!r}", hint=hint)
                option = options[name]
                if option.converter is bool:
                    raise UsageError(f"Boolean flag {name_part!r} does not take a value")
                try:
                    parsed_opts[name].append(option.converter(value))
                except (ValueError, TypeError):
                    raise UsageError(
                        f"Invalid value {value!r} for option '--{name.replace('_', '-')}': expected {_type_name(option.converter)}"
                    )
            else:
                name = token.removeprefix("--").replace("-", "_")
                if name not in options:
                    suggestion = _suggest_option(token, options)
                    hint = f"Did you mean '{suggestion}'?" if suggestion else None
                    raise UsageError(f"Unknown option {token!r}", hint=hint)
                option = options[name]
                if option.converter is bool:
                    parsed_opts[name].append(True)
                else:
                    if i + 1 >= len(args):
                        raise UsageError(f"Option {token!r} requires a value")
                    i += 1
                    try:
                        parsed_opts[name].append(option.converter(args[i]))
                    except (ValueError, TypeError):
                        raise UsageError(
                            f"Invalid value {args[i]!r} for option '--{name.replace('_', '-')}': expected {_type_name(option.converter)}"
                        )

        elif token.startswith("-") and len(token) > 1:
            # Short option: -v  or  -n value
            if token not in alias_map:
                raise UsageError(f"Unknown option {token!r}")
            long_name = alias_map[token]
            option = options[long_name]
            if option.converter is bool:
                parsed_opts[long_name].append(True)
            else:
                if i + 1 >= len(args):
                    raise UsageError(f"Option {token!r} requires a value")
                i += 1
                try:
                    parsed_opts[long_name].append(option.converter(args[i]))
                except (ValueError, TypeError):
                    raise UsageError(
                        f"Invalid value {args[i]!r} for option '--{long_name.replace('_', '-')}': expected {_type_name(option.converter)}"
                    )

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

    # --help / -h: print help and exit immediately
    if parsed_opts.get("help"):
        if subcmd_index is not None:
            subcommand = command.subcommands[args[subcmd_index]]
            subcommand.print_long_help()
        else:
            command.print_long_help()
        return 0

    # --version: only present on root command (injected by Cli)
    if parsed_opts.get("version"):
        version = command.version or "unknown"
        print(f"{command.name} {version}")
        return 0

    # Build updated cascading context for children
    new_context = dict(context)
    for name, option in command.implicit_options.items():
        if option.cascading and name in parsed_opts:
            values = parsed_opts[name]
            if option.converter is bool:
                existing = new_context.get(name, 0)
                new_context[name] = existing + len(values)
            else:
                new_context[name] = values[-1]  # last wins

    # --- Dispatch ---

    if subcmd_index is not None:
        subcommand = command.subcommands[args[subcmd_index]]
        return parse_and_execute_impl(args[subcmd_index + 1 :], subcommand, new_context)

    if command.subcommands and not positionals and not _user_opts(parsed_opts, command):
        command.print_short_help()
        return 0

    if command.subcommands and positionals:
        candidates = list(command.subcommands)
        matches = get_close_matches(positionals[0], candidates, n=1, cutoff=0.6)
        hint = f"Did you mean '{matches[0]}'?" if matches else None
        raise UsageError(f"Unknown subcommand {positionals[0]!r}", hint=hint)

    # Leaf command: assign positionals and call run()
    declared_args = command.arguments
    variadic_arg = declared_args[-1] if declared_args and declared_args[-1].variadic else None
    fixed_args = declared_args[:-1] if variadic_arg else declared_args

    # Check required fixed args are present
    if len(positionals) < len(fixed_args):
        missing = [a.name for a in fixed_args[len(positionals) :]]
        raise UsageError(f"Missing required argument(s): {', '.join(missing)}")

    # Convert fixed positional args
    converted_args = []
    for raw, arg in zip(positionals, fixed_args):
        try:
            converted_args.append(arg.converter(raw))
        except (ValueError, TypeError):
            raise UsageError(
                f"Invalid value {raw!r} for argument '{arg.name}': expected {_type_name(arg.converter)}"
            )

    # Convert variadic remainder
    if variadic_arg:
        remaining = positionals[len(fixed_args) :]
        for raw in remaining:
            try:
                converted_args.append(variadic_arg.converter(raw))
            except (ValueError, TypeError):
                raise UsageError(
                    f"Invalid value {raw!r} for argument '{variadic_arg.name}': expected {_type_name(variadic_arg.converter)}"
                )

    # Only user-defined option values go to run()
    user_kwargs: dict = {}
    for name, option in command.options.items():
        if name in parsed_opts:
            values = parsed_opts[name]
            if option.is_list:
                user_kwargs[name] = values
            else:
                user_kwargs[name] = values if len(values) > 1 else values[0]
        elif option.default is not None:
            user_kwargs[name] = option.default

    return command.run(*converted_args, **user_kwargs) or 0


def _user_opts(parsed_opts: dict, command: "Command") -> bool:
    """Return True if any user-defined options were parsed."""
    return any(k in command.options for k in parsed_opts)
