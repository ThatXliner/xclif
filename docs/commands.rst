Commands
========

A command is a Python function decorated with :func:`~xclif.command.command`. The function's
signature defines the CLI contract.

Defining a command
------------------

.. code-block:: python

   from xclif import command

   @command()
   def greet(name: str, loud: bool = False) -> None:
       """Greet someone."""
       msg = f"Hello, {name}!"
       print(msg.upper() if loud else msg)

This produces::

   Usage: greet [OPTIONS] [NAME]

   Arguments:
     [NAME]    (no description)

   Options:
     --loud, -l    (no description)
     --help, -h    Show this message and exit

Command naming
--------------

The command name is determined by the function name:

.. code-block:: python

   @command()
   def greet(...): ...   # command is named "greet"

In file-based routing, each module file (e.g. ``greet.py``) already carries the intended
name. Using ``_`` as the function name tells Xclif to derive the command name from the
module instead of the function:

.. code-block:: python

   # In greet.py — command is named "greet" (from the module)
   @command()
   def _(...): ...

You can also pass an explicit name to override both:

.. code-block:: python

   @command("deploy")
   def _(...): ...        # command is named "deploy"

Parameter rules
---------------

+-------------------------------+---------------------------+
| Python parameter              | CLI meaning               |
+===============================+===========================+
| ``name: str``                 | Positional argument       |
+-------------------------------+---------------------------+
| ``name: str = "default"``     | ``--name`` option         |
+-------------------------------+---------------------------+
| ``flag: bool = False``        | ``--flag`` boolean flag   |
+-------------------------------+---------------------------+
| ``tags: list[str] = ...``     | Repeatable ``--tags``     |
+-------------------------------+---------------------------+
| ``*files: str``               | Variadic positional args  |
+-------------------------------+---------------------------+

Supported types
---------------

- ``str``, ``int``, ``float``, ``bool``
- ``list[str]``, ``list[int]``, ``list[float]``

Return value
------------

The function should return an ``int`` exit code, or ``None`` (treated as ``0``).

Subcommands (decorator API)
----------------------------

.. code-block:: python

   from xclif.command import Command

   root = Command("myapp", lambda: 0)

   @root.command()
   def greet(name: str) -> None:
       """Greet someone."""
       print(f"Hello, {name}!")

   # Nested group
   config = root.group("config")

   @config.command()
   def get(key: str) -> None:
       """Get a config value."""
       ...

Implicit options
----------------

Every command automatically gets:

- ``--help`` / ``-h`` — print help and exit
- ``--verbose`` / ``-v`` — enable verbose output (cascades to subcommands)

The root command additionally gets ``--version``.
