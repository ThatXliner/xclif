import subprocess
import sys

from xclif import command


@command()
def _() -> int:
    """Show information about installed Poetry plugins.

    Delegates to the real `poetry self show plugins` command.
    """
    return subprocess.call(["poetry", "self", "show", "plugins"], stdout=sys.stdout, stderr=sys.stderr)
