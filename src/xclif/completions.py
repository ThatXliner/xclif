"""Shell completion script generators for xclif applications."""
from __future__ import annotations

__all__ = ["generate_bash", "generate_zsh", "generate_fish", "make_completions_command"]

from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from xclif.command import Command


def _collect_flags(command: Command) -> list[str]:
    """Collect all --option names from a command."""
    all_opts = {**command.implicit_options, **command.options}
    flags = []
    for name, opt in all_opts.items():
        flags.append(f"--{name.replace('_', '-')}")
        flags.extend(opt.aliases)
    return flags


def _sanitize(name: str) -> str:
    """Sanitize a name for use as a shell function identifier."""
    return name.replace("-", "_")


def generate_bash(root: Command) -> str:
    """Generate a bash completion script for the application."""
    app = root.name
    func = f"_complete_{_sanitize(app)}"
    lines = [
        f"{func}() {{",
        "    local cur prev",
        "    COMPREPLY=()",
        '    cur="${COMP_WORDS[COMP_CWORD]}"',
        '    prev="${COMP_WORDS[COMP_CWORD-1]}"',
        "",
    ]

    def _case_entries(cmd: Command, parent_name: str) -> list[str]:
        entries = []
        flags = _collect_flags(cmd)
        subcmds = list(cmd.subcommands.keys())
        words = " ".join(flags + subcmds)
        entries.append(f"        {parent_name})")
        entries.append(f'            COMPREPLY=($(compgen -W "{words}" -- "$cur"))')
        entries.append("            return 0")
        entries.append("            ;;")
        for sub_name, sub_cmd in cmd.subcommands.items():
            entries.extend(_case_entries(sub_cmd, sub_name))
        return entries

    lines.append('    case "$prev" in')
    lines.extend(_case_entries(root, app))
    lines.append("    esac")
    lines.append("")

    # Default fallback: top-level words
    top_flags = _collect_flags(root)
    top_subcmds = list(root.subcommands.keys())
    top_words = " ".join(top_flags + top_subcmds)
    lines.append(f'    COMPREPLY=($(compgen -W "{top_words}" -- "$cur"))')
    lines.append("}")
    lines.append(f"complete -F {func} {app}")
    lines.append("")
    return "\n".join(lines)


def generate_zsh(root: Command) -> str:
    """Generate a zsh completion script for the application."""
    app = root.name
    func = f"_{_sanitize(app)}"
    lines = [
        f"#compdef {app}",
        f"{func}() {{",
        "    local state",
        "    _arguments \\",
    ]

    all_opts = {**root.implicit_options, **root.options}
    for name, opt in all_opts.items():
        flag = f"--{name.replace('_', '-')}"
        desc = opt.description.replace("'", "'\\''")
        lines.append(f"        '{flag}[{desc}]' \\")

    lines.append("        '1: :->subcommand' \\")
    lines.append("        '*::args:->args'")
    lines.append("")
    lines.append("    case $state in")
    lines.append("        subcommand)")
    lines.append("            local subcommands")
    lines.append("            subcommands=(")
    for sub_name, sub_cmd in root.subcommands.items():
        desc = sub_cmd.short_description.replace("'", "'\\''")
        lines.append(f"                '{sub_name}:{desc}'")
    lines.append("            )")
    lines.append("            _describe 'subcommand' subcommands")
    lines.append("            ;;")
    lines.append("        args)")
    lines.append("            case $words[1] in")
    for sub_name, sub_cmd in root.subcommands.items():
        sub_opts = {**sub_cmd.implicit_options, **sub_cmd.options}
        if sub_opts:
            lines.append(f"                {sub_name})")
            args_parts = []
            for oname, oopt in sub_opts.items():
                flag = f"--{oname.replace('_', '-')}"
                desc = oopt.description.replace("'", "'\\''")
                args_parts.append(f"'{flag}[{desc}]'")
            lines.append(f"                    _arguments {' '.join(args_parts)}")
            lines.append("                    ;;")
    lines.append("            esac")
    lines.append("            ;;")
    lines.append("    esac")
    lines.append("}")
    lines.append(f'{func} "$@"')
    lines.append("")
    return "\n".join(lines)


def generate_fish(root: Command) -> str:
    """Generate a fish completion script for the application."""
    app = root.name
    lines = [f"# Completions for {app}", f"complete -c {app} -f"]

    # Top-level subcommands
    for sub_name, sub_cmd in root.subcommands.items():
        desc = sub_cmd.short_description.replace("'", "\\'")
        lines.append(
            f"complete -c {app} -n '__fish_use_subcommand' -a '{sub_name}' -d '{desc}'"
        )

    # Top-level options
    all_opts = {**root.implicit_options, **root.options}
    for name, opt in all_opts.items():
        flag = name.replace("_", "-")
        desc = opt.description.replace("'", "\\'")
        lines.append(f"complete -c {app} -l '{flag}' -d '{desc}'")

    # Per-subcommand options
    for sub_name, sub_cmd in root.subcommands.items():
        sub_opts = {**sub_cmd.implicit_options, **sub_cmd.options}
        for oname, oopt in sub_opts.items():
            flag = oname.replace("_", "-")
            desc = oopt.description.replace("'", "\\'")
            lines.append(
                f"complete -c {app} -n '__fish_seen_subcommand_from {sub_name}' -l '{flag}' -d '{desc}'"
            )

    lines.append("")
    return "\n".join(lines)


def make_completions_command(root: Command) -> "Command":
    """Build the completions subcommand."""
    import sys

    import rich

    from xclif.command import Command, extract_parameters

    _INSTALL_HINTS = {
        "bash": "~/.local/share/bash-completion/completions/{app}",
        "zsh": "~/.zsh/completions/_{app}",
        "fish": "~/.config/fish/completions/{app}.fish",
    }

    _generators = {
        "bash": generate_bash,
        "zsh": generate_zsh,
        "fish": generate_fish,
    }

    def completions_run(shell: Literal["bash", "zsh", "fish"]) -> int:
        """Generate shell completion script

        Prints the completion script for SHELL to stdout.
        Pipe it to the appropriate location for your shell.
        """
        script = _generators[shell](root)
        print(script, end="")
        if sys.stdout.isatty():
            path = _INSTALL_HINTS[shell].format(app=root.name)
            rich.print(
                f"[dim]# To install, run:[/dim]\n"
                f"[bold]  {root.name} completions {shell} > {path}[/bold]",
                file=sys.stderr,
            )
        return 0

    arguments, options = extract_parameters(completions_run)
    return Command("completions", completions_run, arguments, options)
