File-Based Routing
==================

Xclif discovers commands by walking a Python package. The package hierarchy maps directly to the
command hierarchy — no explicit registration required.

How it works
------------

Given this package layout:

.. code-block:: text

   myapp/routes/
   ├── __init__.py       →  myapp          (root command)
   ├── greet.py          →  myapp greet
   └── config/
       ├── __init__.py   →  myapp config   (group command)
       ├── get.py        →  myapp config get
       └── set.py        →  myapp config set

Each module must export exactly one :class:`~xclif.command.Command` object (typically created
with the :func:`~xclif.command.command` decorator):

.. code-block:: python

   # routes/__init__.py  — the root command
   from xclif import command

   @command()
   def myapp() -> None:
       """My awesome CLI."""

.. code-block:: python

   # routes/greet.py
   from xclif import command

   @command()
   def _(name: str) -> None:
       """Greet someone."""
       print(f"Hello, {name}!")

Using ``_`` as the function name tells Xclif to derive the command name from the module name
(``greet`` in this case).

Entry point
-----------

.. code-block:: python

   # __main__.py
   from xclif import Cli
   from . import routes

   cli = Cli.from_routes(routes)
   if __name__ == "__main__":
       cli()

:meth:`~xclif.Cli.from_routes` walks the package, collects all ``Command`` objects, and wires
them into the tree automatically.

Group commands
--------------

A directory with an ``__init__.py`` becomes a *group* command — a command that has subcommands.
The ``__init__.py`` should define the group's help text and any group-level options:

.. code-block:: python

   # routes/config/__init__.py
   from xclif import command

   @command()
   def _() -> None:
       """Manage configuration."""
       # Called when user types `myapp config` with no subcommand.
       # Default behaviour: print help.

.. note::

   A group command cannot declare positional arguments. Positional arguments and subcommands
   are mutually exclusive — Xclif enforces this at definition time.

Plugin discovery
----------------

Third-party packages can contribute subcommands via Python entry points:

.. code-block:: toml

   # In a third-party package's pyproject.toml
   [project.entry-points."myapp.commands"]
   my-plugin = "myplugin.routes:root"

Xclif picks these up automatically when the package is installed.
