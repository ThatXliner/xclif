Configuration
=============

Xclif can read parameter values from config files and environment variables using
``WithConfig[T]``. When a parameter is not supplied on the command line, Xclif checks
these sources in order:

1. **CLI flag** (highest priority)
2. **Environment variable**
3. **Local config file** (cwd — only when ``local_config`` is set)
4. **User config file** (TOML or JSON in the OS config directory)
5. **Default value** (lowest priority)

Basic usage
-----------

Annotate parameters with ``WithConfig[T]`` to opt into config/env resolution:

.. code-block:: python

   from xclif import WithConfig, command

   @command()
   def _(name: WithConfig[str], template: WithConfig[str] = "Hello, {}!") -> None:
       """Greet someone by name."""
       print(template.format(name))

Now ``name`` and ``template`` can be set via the CLI, environment variables, or a config
file — without changing any command logic.

Environment variables
---------------------

By default, the env var name is ``<PREFIX>_<PARAM>``, where ``PREFIX`` is the uppercased
app name:

.. code-block:: bash

   # For an app named "greeter", the param "name" maps to:
   export GREETER_NAME=Alice
   greeter greet   # uses "Alice" from env

Override the prefix on ``Cli``:

.. code-block:: python

   cli = Cli.from_routes(routes, env_prefix="MYAPP")
   # Now looks for MYAPP_NAME instead of GREETER_NAME

Config files
------------

User config (global)
~~~~~~~~~~~~~~~~~~~~

Xclif looks for a user config file in the OS-appropriate config directory (via
`platformdirs <https://github.com/platformdirs/platformdirs>`_):

- Linux: ``~/.config/<app>/config.toml``
- macOS: ``~/Library/Application Support/<app>/config.toml``
- Windows: ``C:\Users\<user>\AppData\Local\<app>\config.toml``

TOML is preferred. If no TOML file exists, Xclif falls back to ``config.json`` in the
same directory. If neither exists, config resolution is skipped.

Example TOML config:

.. code-block:: toml

   name = "Alice"
   template = "Hello, {}!"

Override the app name used for the config directory:

.. code-block:: python

   cli = Cli.from_routes(routes, config_name="my-greeter")

Local config (per-project)
~~~~~~~~~~~~~~~~~~~~~~~~~~

You can also load a config file from the current working directory by setting the
``local_config`` parameter to a filename. This is useful for per-project configuration
that lives alongside the project files:

.. code-block:: python

   cli = Cli.from_routes(routes, local_config=".myapp.toml")

With this, Xclif looks for ``.myapp.toml`` in the current directory. If found, its values
are deep-merged over the user config — local values win, but user-level keys not present
in the local file are preserved. The file must have a ``.toml`` or ``.json`` extension.

If the file does not exist, it is silently skipped. When ``local_config`` is not set
(the default), no cwd lookup is performed.

Auto-injected config subcommands
---------------------------------

When any parameter in your app uses ``WithConfig``, Xclif automatically adds a ``config``
subcommand group with three commands:

- ``myapp config get [KEY...]`` — print all config values, or specific keys
- ``myapp config set KEY VALUE`` — write a value to the config file
- ``myapp config path`` — print the config directory path

``config set`` creates a TOML file if none exists. If only a JSON config file exists, it
writes to JSON instead.

If your app already defines a ``config`` subcommand, the auto-injection is skipped.

To suppress the ``config`` subcommand entirely, pass ``config_command=False``:

.. code-block:: python

   cli = Cli.from_routes(routes, config_command=False)

Conflict detection
------------------

Xclif checks for conflicts at startup (and at compile time with ``xclif compile``). Two
parameters sharing the same config key or env var with **different types** is an error:

.. code-block:: text

   WithConfig conflict: config key 'name' is used as str (in 'greet')
   and int (in 'farewell').

   To fix, rename one of the parameters.

Same key with the **same type** is allowed — the parameters share the config value
intentionally.

Full example
------------

.. code-block:: python

   # routes/greet.py
   from xclif import WithConfig, command

   @command()
   def _(name: WithConfig[str] = "", template: WithConfig[str] = "Hello, {}!") -> None:
       """Greet someone by name."""
       if not name:
           print("Error: provide a name or set one with `myapp config set name <name>`")
           return
       print(template.format(name))

.. code-block:: python

   # __main__.py
   from xclif import Cli
   from . import routes

   cli = Cli.from_routes(routes, local_config=".myapp.toml")
   if __name__ == "__main__":
       cli()

.. code-block:: bash

   # CLI flag (highest priority)
   myapp greet --name Alice

   # Environment variable
   export MYAPP_NAME=Alice
   myapp greet

   # Local config file (.myapp.toml in cwd)
   echo 'name = "Alice"' > .myapp.toml
   myapp greet

   # User config file (OS config directory)
   myapp config set name Alice
   myapp greet

   # Check config
   myapp config get
   myapp config path
