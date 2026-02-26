"""Pytest configuration.

Adds the greeter experiment to sys.path so integration tests can import it
without installing it as a package.
"""

import sys
from pathlib import Path

# Make `greeter` importable
sys.path.insert(0, str(Path(__file__).parent.parent / "experiments" / "greeter"))
