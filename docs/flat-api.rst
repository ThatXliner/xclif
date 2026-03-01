Flat (Imperative) API
=====================

.. warning::

   The flat API is **unstable** — its surface may change between minor versions without
   a deprecation period. For most use cases, prefer :doc:`file-based routing <routing>`,
   which is the idiomatic and stable way to build Xclif CLIs.

   Consider the flat API only if you are:

   * **migrating from Click or Typer** and want to port an existing app incrementally, or
   * **optimising cold-start performance** and can accept the stability trade-off (~12 ms
     saved vs ``from_routes`` by skipping the package walker).

Overview
--------

Instead of relying on the package hierarchy, you can build the command tree imperatively
using :class:`~xclif.command.Command` methods directly.

.. code-block:: python

   from xclif import Cli
   from xclif.command import Command

   root = Command("myapp", lambda: None)
   cli = Cli(root_command=root)

   @root.command()
   def greet(name: str, greeting: str = "Hello") -> None:
       """Greet someone."""
       print(f"{greeting}, {name}!")

   config = root.group("config")

   @config.command()
   def set(key: str, value: str) -> None:
       """Set a config value."""
       print(f"Set {key}={value}")

   @config.command("get")
   def get_cmd(key: str) -> None:
       """Get a config value."""
       print(f"Get {key}")

   if __name__ == "__main__":
       cli()

``Command.command()``
---------------------

A decorator that registers a function as a subcommand of the parent command:

.. code-block:: python

   @parent.command()          # name taken from function name
   def greet(...): ...

   @parent.command("hi")      # explicit name
   def greet(...): ...

The decorated function is converted to a :class:`~xclif.command.Command` and attached to
``parent.subcommands``. The return value is the :class:`~xclif.command.Command` object.

``Command.group()``
-------------------

Creates an empty intermediate command (a *group*) and attaches it as a subcommand:

.. code-block:: python

   config = root.group("config")

   @config.command()
   def set(key: str, value: str) -> None: ...

Groups have no run logic of their own — invoking them without a subcommand prints help.
A group cannot have positional arguments.
