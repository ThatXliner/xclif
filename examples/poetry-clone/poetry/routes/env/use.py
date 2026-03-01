import subprocess
import sys

from xclif import command


@command()
def _(python: str) -> int:
    """Activate or create a virtualenv for a specific Python version.

    PYTHON is the Python version or path to use (e.g. 3.11, python3.11, /usr/bin/python3).
    Delegates to the real `poetry env use` command.
    """
    return subprocess.call(["poetry", "env", "use", python], stdout=sys.stdout, stderr=sys.stderr)
