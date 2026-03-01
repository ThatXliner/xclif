Getting Started
===============

Installation
------------

Xclif requires Python 3.12 or later.

.. code-block:: bash

   pip install xclif

Or with `uv <https://github.com/astral-sh/uv>`_:

.. code-block:: bash

   uv add xclif

Why Xclif?
----------

Xclif is built around two ideas:

1. **File-based routing** — your directory structure *is* your command tree. No registration, no
   boilerplate. Drop a file in the right folder and the command exists.
2. **Function signatures as contracts** — type annotations and default values define the CLI
   automatically. The function *is* the documentation.

Read the :doc:`manifesto` to understand how Xclif compares to Click, Typer, and argparse.

Next Steps
----------

- :doc:`quickstart` — build your first CLI in minutes
- :doc:`routing` — understand file-based routing in depth
- :doc:`api` — full API reference
