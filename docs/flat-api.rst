Flat (Imperative) API
=====================

.. warning::

   The flat API is **unstable** — its surface may change between minor versions without
   a deprecation period. For most use cases, prefer :doc:`file-based routing <routing>`,
   which is the idiomatic and stable way to build Xclif CLIs.

   Consider the flat API only if you are:

   * **migrating from Click or Typer** and want to port an existing app incrementally, or
   * **optimising cold-start performance**, but you should be using the :doc:`compiler <compiler>` for that anyway. Note that performance is not
     a primary focus of Xclif and frankly, if startup latency is a hard constraint,
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

   server = root.group("server")

   @server.command()
   def start(host: str = "localhost", port: int = 8080) -> None:
       """Start the server."""
       print(f"Starting on {host}:{port}")

   @server.command()
   def stop() -> None:
       """Stop the server."""
       print("Stopping server")

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

   @parent.command("hi", "h") # explicit name with alias
   def greet(...): ...

The decorated function is converted to a :class:`~xclif.command.Command` and attached to
``parent.subcommands``. Additional names after the first become aliases. The return value
is the :class:`~xclif.command.Command` object.

``Command.group()``
-------------------

Creates an empty intermediate command (a *group*) and attaches it as a subcommand:

.. code-block:: python

   server = root.group("server")

   @server.command()
   def start(host: str = "localhost") -> None: ...

Groups have no run logic of their own — invoking them without a subcommand prints help.
A group cannot have positional arguments.
