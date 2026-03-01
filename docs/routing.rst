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
(``greet`` in this case). This is the idiomatic style for route files — the filename already
encodes the name, so there is no need to repeat it.

The same command can also be written with an explicit function name or an explicit string
argument — all three are equivalent:

.. code-block:: python

   @command()
   def _(...): ...          # name from module ("greet")

   @command()
   def greet(...): ...      # name from function

   @command("greet")
   def whatever(...): ...   # explicit name (overrides both)

See :doc:`commands` for a full explanation of the naming rules.

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

Best practices
--------------

**Keep routes lean.** ``from_routes`` uses ``pkgutil.walk_packages`` to discover commands, which
*imports every module* it finds in the package. Every file in your routes tree is executed at
startup — including files that define no command. Put business logic, helpers, and shared
utilities in a sibling module *outside* the routes package and import from there:

.. code-block:: text

   myapp/
   ├── __init__.py
   ├── __main__.py
   ├── utils.py          ← helpers live here, imported only when needed
   ├── db.py             ← same — not walked by from_routes
   └── routes/
       ├── __init__.py
       ├── greet.py      ← imports from myapp.utils as needed
       └── config/
           ├── __init__.py
           ├── get.py
           └── set.py

.. code-block:: python

   # routes/greet.py
   from xclif import command
   from myapp.utils import format_greeting   # imported only when greet.py is loaded

   @command()
   def _(name: str) -> None:
       """Greet someone."""
       print(format_greeting(name))

If you put a utility module *inside* the routes package, it will be imported on every invocation
even when the user runs a completely unrelated command.

**Prefix private modules with ``_`` (future support).** Xclif does not yet filter private modules,
but following the convention now means your code will benefit automatically once support is added.
Until then, keep helper code outside the routes package entirely.

Plugin discovery
----------------

Third-party packages can contribute subcommands via Python entry points:

.. code-block:: toml

   # In a third-party package's pyproject.toml
   [project.entry-points."myapp.commands"]
   my-plugin = "myplugin.routes:root"

Xclif picks these up automatically when the package is installed.
