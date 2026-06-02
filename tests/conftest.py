"""Pytest configuration.

Adds the examples to sys.path so integration tests can import them
without installing them as packages.
"""

import stat
import sys
from pathlib import Path

import pytest

_examples = Path(__file__).parent.parent / "examples"

# Make `greeter` importable
sys.path.insert(0, str(_examples / "greeter"))
# Make `poetry` (poetry-clone) importable
sys.path.insert(0, str(_examples / "poetry-clone"))


@pytest.fixture
def make_plugin_exe(tmp_path):
    """Factory fixture: create a platform-appropriate plugin executable.

    Returns a callable::

        exe_path = make_plugin_exe(root="myapp", name="deploy", content=None)

    On Windows a ``.bat`` file is created (required for ``shutil.which``),
    on POSIX a plain file with the execute bit set.  When *content* is
    *None*, a simple ``exit 0`` script is written.
    """

    def _make(root: str = "myapp", name: str = "deploy", content: str | None = None):
        if sys.platform == "win32":
            exe = tmp_path / f"{root}-{name}.bat"
            exe.write_text(content if content is not None else "@exit /b 0\n")
        else:
            exe = tmp_path / f"{root}-{name}"
            exe.write_text(content if content is not None else "#!/bin/sh\nexit 0\n")
            exe.chmod(stat.S_IRWXU)
        return exe

    return _make
