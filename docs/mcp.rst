MCP Server Mode
===============

Xclif can expose your CLI as `Model Context Protocol (MCP) <https://modelcontextprotocol.io>`_
tools. This lets AI agents and MCP clients invoke your commands through a structured
interface — no shell parsing required.

Each leaf command in your CLI tree becomes an MCP tool with typed parameters derived
from the command's signature.

Installation
------------

The MCP feature requires an optional dependency:

.. code-block:: bash

   pip install xclif[mcp]

   # Or if using uv:
   # uv add xclif[mcp]

Usage
-----

There are two ways to start the MCP server:

1. **Auto-injected ``mcp`` subcommand** — when the ``mcp`` package is installed,
   Xclif automatically adds a ``mcp`` subcommand to your CLI:

   .. code-block:: bash

       myapp mcp

   This starts a stdio-based MCP server. Configure your MCP client to run
   ``myapp mcp`` as the command.

2. **Programmatic** — call :meth:`~xclif.Cli.serve_mcp` on your ``Cli`` instance:

   .. code-block:: python

       from xclif import Cli
       from . import routes

       cli = Cli.from_routes(routes)
       cli.serve_mcp()  # blocks, serving over stdio

   This is useful when you need to customize the ``Cli`` before serving.

How it works
------------

When the MCP server starts, Xclif walks the command tree and registers every
leaf command (commands with no subcommands) as an MCP tool.

- **Tool names** are the command path joined by underscores, e.g.
  ``config_get``, ``config_set``, ``deploy``.
- **Tool parameters** map 1:1 to the command's positional arguments and options.
  Positional arguments become required parameters; options become optional
  parameters with their default values.
- **Return value** is the command's stdout as a string. Non-zero exit codes
  raise a ``RuntimeError`` with the command's stderr output.

Hidden subcommands (``completions``, ``mcp``) and alias entries are excluded
from the tool list.

Example
-------

Given this CLI tree::

   myapp
   ├── greet NAME
   ├── config
   │   ├── get
   │   └── set KEY VALUE
   └── deploy

The MCP server exposes three tools:

- ``greet`` (parameter: ``name: str``)
- ``config_get`` (no parameters)
- ``config_set`` (parameters: ``key: str``, ``value: str``)
- ``deploy`` (no parameters)

Limitations
-----------

- The server uses **stdio transport** only (stdin/stdout). Network transports
  are not currently supported.
- **Stderr is captured** and raised as ``RuntimeError`` on failure, so error
  output doesn't corrupt the MCP stdio protocol.
- Requires the ``mcp`` package (``pip install xclif[mcp]``).
