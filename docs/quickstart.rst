Quick Start
===========

This page walks you through building a minimal Xclif CLI from scratch.

Step 1: Define your routes
--------------------------

Your directory structure *is* your command tree:

.. code-block:: text

   myapp/
   ├── __init__.py
   ├── __main__.py
   └── routes/
       ├── __init__.py       →  myapp
       ├── greet.py          →  myapp greet
       └── config/
           ├── __init__.py   →  myapp config
           ├── get.py        →  myapp config get
           └── set.py        →  myapp config set

Step 2: Write commands as functions
------------------------------------

.. code-block:: python

   # routes/greet.py
   from xclif import command

   @command()
   def _(name: str, template: str = "Hello, {}!") -> None:
       """Greet someone by name."""
       print(template.format(name))

The mapping rules are simple:

- **No default** → positional argument (``name``)
- **Has default** → ``--template`` option
- **Docstring** → help text
- **Type annotation** → parser and type coercion

The function signature *is* the CLI contract.

Step 3: Three-line entry point
-------------------------------

.. code-block:: python

   # __main__.py
   from xclif import Cli
   from . import routes

   cli = Cli.from_routes(routes)
   if __name__ == "__main__":
       cli()

Run it:

.. code-block:: bash

   python -m myapp greet Alice
   # Hello, Alice!

   python -m myapp greet Alice --template "Hi, {}!"
   # Hi, Alice!

   python -m myapp --help

Decorator API (alternative)
-----------------------------

For smaller CLIs, you can build the command tree directly without file-based routing:

.. code-block:: python

   from xclif import command, Cli
   from xclif.command import Command

   root = Command("myapp", lambda: 0)

   @root.command()
   def greet(name: str) -> None:
       """Greet someone."""
       print(f"Hello, {name}!")

   config = root.group("config")

   @config.command()
   def get(key: str) -> None:
       """Read a config value."""
       ...

   cli = Cli(root_command=root)
   cli()

Testing
-------

Commands can be tested without mocking ``sys.argv``:

.. code-block:: python

   def test_greet(capsys):
       cli.root_command.execute(["greet", "Alice"])
       assert capsys.readouterr().out == "Hello, Alice!\n"
