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


cli = Cli(root_command=root)

if __name__ == "__main__":
    cli()
