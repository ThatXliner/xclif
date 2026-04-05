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

   Greet someone.
   Usage: greet [OPTIONS] [NAME]

   Arguments:
     [name]        No description

   Options:
     --help, -h     Show this help message and exit
     --verbose, -v  Increase log verbosity (repeatable up to 3 times)
     --colors       Control color output (always|never|auto)
     --loud, -l     No description

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
- ``Literal["a", "b", "c"]`` — constrained string choices (see :ref:`constrained-choices`)

Return value
------------

The function should return an ``int`` exit code, or ``None`` (treated as ``0``).

Implicit options
----------------

Every command automatically gets:

- ``--help`` / ``-h`` — print help and exit
- ``--verbose`` / ``-v`` — increase verbosity; repeatable up to 3 times (``-vvv``)
- ``--colors`` — control color output (``always``, ``never``, or ``auto``)

The root command additionally gets ``--version``.

Both ``--verbose`` and ``--colors`` **cascade**: if set at any level, the value is
automatically inherited by all subcommands. So ``myapp --verbose subcommand`` and
``myapp subcommand --verbose`` are equivalent, and ``myapp -vv subcommand`` gives
the subcommand a verbosity level of 2.

Building subcommand trees imperatively
---------------------------------------

If you need to build the command tree in code rather than via file-based routing, see
:doc:`flat-api`.
