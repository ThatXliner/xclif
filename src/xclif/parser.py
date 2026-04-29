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

import inspect
import os
from collections import defaultdict
from difflib import get_close_matches
from typing import TYPE_CHECKING

from xclif.config import resolve_key
from xclif.definition import Argument, _DefinitionOption
from xclif.errors import UsageError
from xclif.context import Context, _reset_context, _set_context

if TYPE_CHECKING:
    from xclif.command import Command


def _build_alias_map(options: dict[str, _DefinitionOption]) -> dict[str, str]:
    """Build a mapping from short alias → param key."""
    alias_map: dict[str, str] = {}
    for long_name, option in options.items():
        for alias in option.aliases:
            alias_map[alias] = long_name
    return alias_map


def _build_flag_map(options: dict[str, _DefinitionOption]) -> dict[str, str]:
    """Build a mapping from CLI flag name (underscored) → param key.

    Handles Option(name=...) overrides: --dry-run maps to param key dry_run,
    but --from (overridden via Option(name="from")) maps to param key from_ref.
    """
    flag_map: dict[str, str] = {}
    for param_key, option in options.items():
        cli_name = option.name.replace("-", "_")
        flag_map[cli_name] = param_key
    return flag_map


def _type_name(converter: type) -> str:
    """Return a human-readable name for a type converter."""
    return getattr(converter, "__name__", str(converter))


def _convert_option_value(option: _DefinitionOption, raw: str) -> object:
    """Convert and validate a raw option value."""
    try:
        value = option.converter(raw)
    except (ValueError, TypeError):
        raise UsageError(
            f"Invalid value {raw!r} for option '--{option.name.replace('_', '-')}': expected {_type_name(option.converter)}"
        )
    if option.choices is not None and value not in option.choices:
        raise UsageError(
            f"Invalid value {raw!r} for option '--{option.name.replace('_', '-')}': "
            f"expected one of: {', '.join(option.choices)}"
        )
    return value


def _suggest_option(name: str, options: dict[str, _DefinitionOption]) -> str | None:
    """Suggest a close match for an unknown option name."""
    candidates = [f"--{opt.name.replace('_', '-')}" for opt in options.values()]
    matches = get_close_matches(name, candidates, n=1, cutoff=0.6)
    return matches[0] if matches else None


def _parse_token_stream(
    options: dict[str, _DefinitionOption],
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
    flag_map = _build_flag_map(options)
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
                flag = name_part.removeprefix("--").replace("-", "_")
                name = flag_map.get(flag)
                if name is None:
                    suggestion = _suggest_option(name_part, options)
                    hint = f"Did you mean '{suggestion}'?" if suggestion else None
                    raise UsageError(f"Unknown option {name_part!r}", hint=hint)
                option = options[name]
                if option.converter is bool:
                    raise UsageError(f"Boolean flag {name_part!r} does not take a value")
                parsed_opts[name].append(_convert_option_value(option, value))
            else:
                flag = token.removeprefix("--").replace("-", "_")
                name = flag_map.get(flag)
                if name is None:
                    suggestion = _suggest_option(token, options)
                    hint = f"Did you mean '{suggestion}'?" if suggestion else None
                    raise UsageError(f"Unknown option {token!r}", hint=hint)
                option = options[name]
                if option.converter is bool:
                    parsed_opts[name].append(True)
                elif option.optional_value is not None:
                    parsed_opts[name].append(option.optional_value)
                else:
                    if i + 1 >= len(args):
                        raise UsageError(f"Option {token!r} requires a value")
                    i += 1
                    parsed_opts[name].append(_convert_option_value(option, args[i]))

        elif token.startswith("-") and len(token) > 1:
            # Short option: -v  or  -n value
            if token not in alias_map:
                raise UsageError(f"Unknown option {token!r}")
            long_name = alias_map[token]
            option = options[long_name]
            if option.converter is bool:
                parsed_opts[long_name].append(True)
            elif option.optional_value is not None:
                parsed_opts[long_name].append(option.optional_value)
            else:
                if i + 1 >= len(args):
                    raise UsageError(f"Option {token!r} requires a value")
                i += 1
                parsed_opts[long_name].append(_convert_option_value(option, args[i]))

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
    all_options = {**command.options, **command.implicit_options}

    positionals, parsed_opts, subcmd_index = _parse_token_stream(
        all_options, command.subcommands, args
    )

    # --- Act on implicit options first, before any dispatch ---

    # --help / -h: print help and exit immediately
    # Supports --help (auto-detect), --help=plain, --help=rich, --help=agent
    if parsed_opts.get("help"):
        help_mode = parsed_opts["help"][-1]  # last wins
        if help_mode not in ("auto", "plain", "rich", "agent"):
            raise UsageError(
                f"Invalid help mode {help_mode!r}",
                hint="Valid modes: plain, rich, agent",
            )
        target = command.subcommands[args[subcmd_index]] if subcmd_index is not None else command
        if help_mode == "agent":
            target.print_agent_help()
        elif help_mode == "rich":
            target.print_long_help(force_rich=True)
        elif help_mode == "plain":
            target.print_long_help(force_rich=True, force_plain=True)
        else:
            target.print_long_help()
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

    # Convert fixed positional args (CLI-supplied)
    converted_args = []
    for raw, arg in zip(positionals, fixed_args):
        try:
            converted_args.append(arg.converter(raw))
        except (ValueError, TypeError):
            raise UsageError(
                f"Invalid value {raw!r} for argument '{arg.name}': expected {_type_name(arg.converter)}"
            )

    # Fill missing positionals from WithConfig (env/config) — already converted
    for i in range(len(converted_args), len(fixed_args)):
        arg = fixed_args[i]
        resolved = _resolve_with_config(arg.name, arg, new_context)
        if resolved is not _CONFIG_MISSING:
            converted_args.append(resolved)
        else:
            break

    # Check required fixed args are present
    if len(converted_args) < len(fixed_args):
        missing = [a.name for a in fixed_args[len(converted_args) :]]
        raise UsageError(f"Missing required argument(s): {', '.join(missing)}")

    # Convert variadic remainder
    variadic_items: list = []
    if variadic_arg:
        remaining = positionals[len(fixed_args) :]
        for raw in remaining:
            try:
                variadic_items.append(variadic_arg.converter(raw))
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
        else:
            # Try WithConfig resolution: env var > config file > default
            resolved = _resolve_with_config(name, option, new_context)
            if resolved is not _CONFIG_MISSING:
                if option.is_list and not isinstance(resolved, list):
                    resolved = [resolved]
                user_kwargs[name] = resolved
            elif option.default is not None:
                user_kwargs[name] = option.default

    token = _set_context(Context(new_context))
    try:
        if variadic_arg:
            # When a variadic *args parameter exists, interleave fixed args and
            # options in signature order, then append variadic items positionally.
            # Passing options as **kwargs alongside extra positionals causes
            # "got multiple values" if option parameters sit between fixed args
            # and *args in the function signature.
            sig = inspect.signature(command.run)
            positional_call: list = []
            remaining_kwargs: dict = dict(user_kwargs)
            fixed_iter = iter(converted_args)
            arg_names = {a.name for a in fixed_args}
            for param_name, param in sig.parameters.items():
                if param.kind == param.VAR_POSITIONAL:
                    break
                if param.kind == param.VAR_KEYWORD:
                    break
                if param_name in arg_names:
                    positional_call.append(next(fixed_iter))
                elif param_name in remaining_kwargs:
                    positional_call.append(remaining_kwargs.pop(param_name))
            return command.run(*positional_call, *variadic_items, **remaining_kwargs) or 0
        return command.run(*converted_args, **user_kwargs) or 0
    finally:
        _reset_context(token)


def _user_opts(parsed_opts: dict, command: "Command") -> bool:
    """Return True if any user-defined options were parsed."""
    return any(k in command.options for k in parsed_opts)


_CONFIG_MISSING = object()

_BOOL_TRUE = frozenset({"1", "true", "yes", "on"})
_BOOL_FALSE = frozenset({"0", "false", "no", "off"})


def _parse_bool_string(raw: str, source: str) -> bool:
    """Parse a string as a boolean, raising UsageError for ambiguous values."""
    lower = raw.lower()
    if lower in _BOOL_TRUE:
        return True
    if lower in _BOOL_FALSE:
        return False
    raise UsageError(
        f"Invalid boolean value {raw!r} from {source}: "
        f"expected one of: {', '.join(sorted(_BOOL_TRUE | _BOOL_FALSE))}"
    )


def _resolve_with_config(
    name: str,
    option_or_arg: "_DefinitionOption | Argument",
    context: dict,
) -> object:
    """Try to resolve a WithConfig parameter from env var or config file.

    Returns _CONFIG_MISSING if no value is found.
    """
    cfg = option_or_arg.config
    if cfg is None:
        return _CONFIG_MISSING

    env_prefix = context.get("env_prefix")
    config_data = context.get("config_data", {})

    # Try env var
    env_var = f"{env_prefix}_{name.upper()}" if env_prefix else None
    if env_var:
        raw = os.environ.get(env_var)
        if raw is not None:
            if option_or_arg.converter is bool:
                return _parse_bool_string(raw, f"env var '{env_var}'")
            try:
                return option_or_arg.converter(raw)
            except (ValueError, TypeError):
                raise UsageError(
                    f"Invalid value {raw!r} from env var '{env_var}': "
                    f"expected {_type_name(option_or_arg.converter)}"
                )

    # Try config file
    config_key = name
    value = resolve_key(config_data, config_key, _CONFIG_MISSING)
    if value is not _CONFIG_MISSING:
        if isinstance(value, option_or_arg.converter):
            return value
        try:
            return option_or_arg.converter(value)
        except (ValueError, TypeError):
            raise UsageError(
                f"Invalid value {value!r} from config key '{config_key}': "
                f"expected {_type_name(option_or_arg.converter)}"
            )

    return _CONFIG_MISSING
