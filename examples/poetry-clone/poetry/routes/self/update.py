import subprocess
import sys

from xclif import command


@command()
def _(preview: bool = False) -> int:
    """Update Poetry to the latest version.

    Pass --preview to allow installing pre-release versions.
    Delegates to the real `poetry self update` command.
    """
    cmd = ["poetry", "self", "update"]
    if preview:
        cmd.append("--preview")
    return subprocess.call(cmd, stdout=sys.stdout, stderr=sys.stderr)
