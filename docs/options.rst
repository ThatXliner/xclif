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

The ``--`` separator
---------------------

``--`` stops all option parsing. Everything after it is treated as raw positional arguments::

   myapp run -- --some-flag-for-subprocess
