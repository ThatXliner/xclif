import importlib
from pathlib import Path

from xclif import Cli
from xclif.command import Command
from xclif.errors import UsageError

def _root() -> None:
    """Xclif developer tools."""


root = Command("xclif", _root)


@root.command()
def compile(routes_module: str, output: str = "") -> None:
    """Compile a routes package into a static manifest file.

    Walks ROUTES_MODULE once and writes a ``_xclif_manifest.py`` next to the
    routes package (or into OUTPUT if given).  Use ``Cli.from_manifest()`` to
    load the manifest at runtime instead of ``Cli.from_routes()``, skipping
    the filesystem walk on every invocation.
    """
    try:
        routes = importlib.import_module(routes_module)
    except ImportError as exc:
        raise UsageError(f"Cannot import {routes_module!r}: {exc}") from exc

    from xclif.compiler import compile_routes

    output_dir = Path(output) if output else None
    output_path = compile_routes(routes, output_dir=output_dir)
    print(f"Written: {output_path}")


@root.command("from-openapi")
def from_openapi(spec: str, base_url: str = "", output: str = "") -> None:
    """Build an xclif CLI from an OpenAPI JSON spec.

    Parses SPEC (a local JSON file or HTTP(S) URL) and prints the
    generated command tree.  Use ``Cli.from_openapi()`` in code to use
    the generated CLI programmatically.
    """
    from xclif.from_openapi import _build_command_tree, load_spec

    spec_data = load_spec(spec)
    root_cmd = _build_command_tree(spec_data)

    if output:
        _generate_openapi_cli(output, root_cmd, base_url)
    else:
        # Print the command tree
        _print_command_tree(root_cmd)

    print(f"\nLoaded {len(spec_data.get('paths', {}))} path(s) from {spec!r}")


def _print_command_tree(cmd: Command, indent: int = 0) -> None:
    """Print a tree view of the command hierarchy."""
    prefix = "  " * indent
    desc = cmd.short_description
    if desc and desc != "No description":
        print(f"{prefix}{cmd.name}  # {desc}")
    else:
        print(f"{prefix}{cmd.name}")
    seen: set[int] = set()
    for name, sub in cmd.subcommands.items():
        if id(sub) not in seen:
            seen.add(id(sub))
            _print_command_tree(sub, indent + 1)


def _generate_openapi_cli(output: str, root_cmd: Command, base_url: str) -> None:
    """Generate a standalone Python CLI script from the OpenAPI-derived command tree."""
    # Simple code generation for the static manifest + CLI entry point
    output_path = Path(output)
    root_name = root_cmd.name

    lines = [
        "#!/usr/bin/env python3",
        f'"""CLI generated from OpenAPI spec — {root_name}."""',
        "",
        "from pathlib import Path",
        "",
        "from xclif import Cli, command",
        "from xclif.command import Command",
        "from xclif.from_openapi import _build_command_tree, load_spec",
        "",
        f'SPEC_PATH = Path(__file__).with_suffix(".json")',
        "",
        "def main() -> None:",
        "    if SPEC_PATH.is_file():",
        "        cli = Cli.from_openapi(str(SPEC_PATH)",
    ]

    if base_url:
        lines.append(f"            base_url={base_url!r},")

    lines.extend([
        "        )",
        "        cli()",
        "    else:",
        f'        print(f"Error: spec file not found: {{SPEC_PATH}}")',
        "        sys.exit(1)",
        "",
        "",
        'if __name__ == "__main__":',
        "    import sys",
        "    main()",
    ])

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    output_path.chmod(0o755)
    print(f"Generated CLI script: {output}")


cli = Cli(root_command=root)

if __name__ == "__main__":
    cli()
