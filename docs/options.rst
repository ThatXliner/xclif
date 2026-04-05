Options & Arguments
===================

Arguments
---------

Positional arguments are parameters with no default value:

.. code-block:: python

   @command()
   def copy(src: str, dst: str) -> None:
       """Copy SRC to DST."""

Usage::

   myapp copy file.txt /tmp/

Variadic arguments collect all remaining tokens:

.. code-block:: python

   @command()
   def add(*files: str) -> None:
       """Stage files."""

Usage::

   myapp add file1.py file2.py file3.py

Options
-------

Parameters with a default value become CLI options:

.. code-block:: python

   @command()
   def greet(name: str, template: str = "Hello, {}!") -> None:
       """Greet someone."""
       print(template.format(name))

Usage::

   myapp greet Alice
   myapp greet Alice --template "Hi, {}!"
   myapp greet Alice -t "Hi, {}!"   # auto-generated short alias

Boolean flags
-------------

``bool`` options default to ``False`` and are toggled by passing the flag:

.. code-block:: python

   @command()
   def build(release: bool = False) -> None:
       """Build the project."""

Usage::

   myapp build          # release = False
   myapp build --release  # release = True

Repeatable options
------------------

``list[T]`` options accept the flag multiple times:

.. code-block:: python

   @command()
   def publish(tag: list[str] = []) -> None:
       """Publish with tags."""

Usage::

   myapp publish --tag latest --tag stable
   # tag = ["latest", "stable"]

Short aliases
-------------

Xclif auto-generates a single-char short alias for each option using the first available
character of the option name. ``--template`` → ``-t``, ``--release`` → ``-r``, etc.

If the first character is taken by an implicit option (``-h``, ``-v``), Xclif tries subsequent
characters. Explicit alias control is planned for 0.2.0 via ``Annotated`` metadata.

Interspersed options
--------------------

Options and positional arguments may appear in any order at the same command level::

   myapp greet --template "Hi!" Alice
   myapp greet Alice --template "Hi!"  # both valid

Config-backed parameters
------------------------

Parameters annotated with ``WithConfig[T]`` fall back to environment variables and config
files when not supplied on the CLI:

.. code-block:: python

   from xclif import WithConfig, command

   @command()
   def _(name: WithConfig[str], greeting: WithConfig[str] = "Hello") -> None:
       ...

See :doc:`config` for full details on priority order, env var naming, and config file format.

Per-parameter metadata
----------------------

Use ``Arg`` and ``Option`` inside ``Annotated`` to attach descriptions or override
display names and flag names:

.. code-block:: python

   from typing import Annotated
   from xclif import Arg, Option, command

   @command()
   def copy(
       src: Annotated[str, Arg(description="Source file", name="SRC")],
       dst: Annotated[str, Arg(description="Destination path", name="DST")],
   ) -> None:
       """Copy SRC to DST."""

   @command()
   def build(
       dry_run: Annotated[bool, Option(description="Skip execution", name="dry-run")] = False,
   ) -> None:
       """Build the project."""

``Arg`` fields:

- ``description`` — text shown next to the argument in help output
- ``name`` — display name in help (e.g. ``SRC`` instead of ``src``); does not affect parsing

``Option`` fields:

- ``description`` — text shown next to the flag in help output
- ``name`` — overrides the CLI flag name (e.g. ``dry-run`` → ``--dry-run``). The Python
  kwarg name passed to the function is unchanged.

Both can be combined with ``WithConfig``. Note that ``WithConfig[str]`` is sugar for
``Annotated[str, WithConfig()]`` — when combining with ``Arg`` or ``Option`` you must
use the full ``Annotated`` form:

.. code-block:: python

   name: Annotated[str, Arg(description="Person to greet"), WithConfig()]

.. _constrained-choices:

Constrained choices
-------------------

Use ``Literal`` to restrict an argument or option to a fixed set of string values.
Xclif validates the input and shows the valid choices in help output:

.. code-block:: python

   from typing import Annotated, Literal
   from xclif import command

   @command()
   def completions(shell: Literal["bash", "zsh", "fish"]) -> None:
       """Generate shell completion script."""
       ...

Usage::

   myapp completions bash    # ok
   myapp completions nushell # error: expected one of: bash|zsh|fish

Help output displays the choices inline::

   Usage: myapp completions [bash|zsh|fish]

Only ``Literal`` of strings is supported. Mixed-type Literals (e.g.
``Literal["a", 1]``) are not supported and will raise a ``TypeError`` at
command construction time.

The ``--`` separator
---------------------

``--`` stops all option parsing. Everything after it is treated as raw positional arguments::

   myapp run -- --some-flag-for-subprocess
