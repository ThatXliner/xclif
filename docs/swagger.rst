Swagger/OpenAPI
===============

Xclif can generate a fully functional CLI from any `OpenAPI 3.0`_ (formerly Swagger) specification.
Each API endpoint becomes a subcommand, path parameters become positional arguments, query
parameters become CLI options, and request bodies are accepted via ``--data``.

Entry point
-----------

.. code-block:: python

   from xclif import Cli

   cli = Cli.from_swagger("petstore.json")
   cli()

This parses the spec, builds the command tree, and lets you interact with the API from your
terminal. HTTP requests are made using Python's built-in ``urllib`` — no extra dependencies
required.

Command tree
------------

Given an OpenAPI spec like this:

.. code-block:: yaml

   paths:
     /pets:
       get:
         operationId: listPets
         parameters:
           - name: limit
             in: query
             schema:
               type: integer
       post:
         operationId: createPet
         requestBody:
           content:
             application/json:
               schema:
                 type: object
     /pets/{petId}:
       get:
         operationId: getPetById
         parameters:
           - name: petId
             in: path
             required: true
             schema:
               type: string

The resulting CLI looks like::

   pet-store list_pets [OPTIONS]
   pet-store create_pet [OPTIONS]
   pet-store get_pet_by_id <petId>

Static path segments become group commands. ``operationId`` determines the leaf command name
(converted to ``snake_case``). Path parameters become positional arguments; query parameters
become ``--options``.

Cascading options
-----------------

Root-level options control HTTP behaviour and are inherited by all subcommands:

.. list-table::
   :header-rows: 1

   * - Option
     - Default
     - Description
   * - ``--api-key``
     - ``""``
     - API key for authentication (also settable via ``<PREFIX>_API_KEY`` env var)
   * - ``--api-key-header``
     - ``Authorization``
     - Header name for the API key
   * - ``--base-url``
     - from spec ``servers[0].url``
     - Override the API base URL
   * - ``--timeout``
     - ``30``
     - Request timeout in seconds
   * - ``--insecure``
     - ``False``
     - Skip SSL verification
   * - ``--raw``
     - ``False``
     - Raw response output (no JSON formatting)

From the command line
---------------------

You can inspect the generated command tree without writing any code:

.. code-block:: bash

   xclif from-swagger petstore.json

This prints the hierarchy of commands, subcommands, and options. Pass ``--output <file>`` to
generate a standalone Python script:

.. code-block:: bash

   xclif from-swagger petstore.json --output mycli.py
   python mycli.py --help

API reference
-------------

.. autoclass:: xclif.Cli
   :no-undoc-members:

   .. automethod:: from_swagger

.. _OpenAPI 3.0: https://spec.openapis.org/oas/v3.0.3
