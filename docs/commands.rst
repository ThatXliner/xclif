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

There are three ways to name a command, listed in order of precedence:

**1. Explicit name** — pass a string to ``@command()``:

.. code-block:: python

   @command("deploy")
   def whatever(...): ...   # command is named "deploy"

The string argument wins regardless of the function name or module name.

**2. Function name** — omit the argument and name the function:

.. code-block:: python

   @command()
   def greet(...): ...   # command is named "greet"

This is the most natural form for the decorator/flat API.

**3. Module inference** — name the function ``_``:

.. code-block:: python

   # In routes/greet.py — command is named "greet" (from the module)
   @command()
   def _(...): ...

When the function is named ``_``, Xclif derives the command name from the last component
of the module's dotted path. This is the idiomatic style for file-based routing: the
filename already carries the command name, so duplicating it in the function name is
unnecessary.

All three forms are equivalent in what they produce — the only difference is *where* the
name comes from. In practice, prefer the module-inference style (``def _``) in route
files and the function-name style (``def greet``) in the decorator API.

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

   # Nested subcommand — intermediate group created automatically
   @root.command(["config", "get"])
   def get(key: str) -> None:
       """Get a config value."""
       ...

Implicit options
----------------

Every command automatically gets:

- ``--help`` / ``-h`` — print help and exit
- ``--verbose`` / ``-v`` — enable verbose output (cascades to subcommands)

The root command additionally gets ``--version``.
