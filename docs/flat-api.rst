Flat (Imperative) API
=====================

.. warning::

   The flat API is **unstable** — its surface may change between minor versions without
   a deprecation period. For most use cases, prefer :doc:`file-based routing <routing>`,
   which is the idiomatic and stable way to build Xclif CLIs.

   Consider the flat API only if you are:

   * **migrating from Click or Typer** and want to port an existing app incrementally, or
   * **optimising cold-start performance** and can accept the stability trade-off (~12 ms
     saved vs ``from_routes`` by skipping the package walker). Note that performance is not
     a primary focus of Xclif — and frankly, if startup latency is a hard constraint,
     Python is probably the wrong tool for the job.

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

   @root.command(["config", "set"])
   def set(key: str, value: str) -> None:
       """Set a config value."""
       print(f"Set {key}={value}")

   @root.command(["config", "get"])
   def get_cmd(key: str) -> None:
       """Get a config value."""
       print(f"Get {key}")

   if __name__ == "__main__":
       cli()

``Command.command()``
---------------------

A decorator that registers a function as a subcommand of the parent command.

**Direct subcommand** — pass a string or nothing:

.. code-block:: python

   @parent.command()          # name taken from function name
   def greet(...): ...

   @parent.command("hi")      # explicit name
   def greet(...): ...

**Nested subcommand** — pass a list of strings. Intermediate group commands are
created automatically:

.. code-block:: python

   @root.command(["config", "set"])
   def set(key: str, value: str) -> None: ...

   @root.command(["config", "get"])
   def get(key: str) -> None: ...

The last element of the list is the command name. Any intermediate segments become
empty group commands (no run logic — invoking them without a subcommand prints help).
A group cannot have positional arguments.

The decorated function is converted to a :class:`~xclif.command.Command` and returned.
