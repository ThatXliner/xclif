"""Pytest configuration.

Adds the examples to sys.path so integration tests can import them
without installing them as packages.
"""

import sys
from pathlib import Path

_examples = Path(__file__).parent.parent / "examples"

# Make `greeter` importable
sys.path.insert(0, str(_examples / "greeter"))
# Make `poetry` (poetry-clone) importable
sys.path.insert(0, str(_examples / "poetry-clone"))
