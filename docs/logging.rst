Logging
=======

Xclif wires Python's standard :mod:`logging` to its built-in ``-v`` /
``--verbose`` flag. You write ordinary log calls; Xclif decides which records
are shown and renders them with `Rich <https://rich.readthedocs.io/>`_.

Basic usage
-----------

Import the bundled ``log`` and call it. During a command run, Xclif has already
set the level from ``--verbose`` and attached a Rich handler:

.. code-block:: python

   from xclif import command, log

   @command()
   def _(target: str) -> None:
       """Deploy to a target."""
       log.info("Connecting to %s...", target)    # shown at -v
       log.debug("Resolving %s...", target)        # shown at -vv

Run it:

.. code-block:: bash

   myapp deploy prod          # warnings and errors only
   myapp deploy prod -v       # + info
   myapp deploy prod -vv      # + debug, with file:line locations
   myapp deploy prod -vvv     # + timestamps (verbose formatter)

``log`` provides the usual methods — ``debug``, ``info``, ``warning``,
``error``, ``critical``, ``exception``, and ``log`` — accepting the same
``%``-style arguments as the standard library.

It is not a logger of its own: on each call it resolves the **calling module's**
``__name__`` and forwards to ``logging.getLogger(<that module>)``. So records
carry the right source name and ``file:line`` no matter which module imported
``log``, and everything still flows through the standard :mod:`logging` tree.

Named loggers (escape hatch)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When you want an explicitly named logger — for instance to set a per-component
level — reach for the standard library directly. ``get_logger`` is a thin
wrapper for readers who prefer to import everything from ``xclif``:

.. code-block:: python

   import logging
   logger = logging.getLogger(__name__)   # the standard way

   from xclif import get_logger
   logger = get_logger(__name__)          # identical, single import

Both compose with ``log``: they share the same handler and level that Xclif
installs on the root logger.

Verbosity-to-level mapping
--------------------------

Each ``-v`` raises the verbosity count, which maps to a standard logging level
and a progressively more detailed Rich formatter:

.. list-table::
   :header-rows: 1
   :widths: 10 20 40

   * - Flag
     - Level shown
     - Formatter detail
   * - *(none)*
     - ``WARNING``
     - message only
   * - ``-v``
     - ``INFO``
     - message only
   * - ``-vv``
     - ``DEBUG``
     - + file/line locations
   * - ``-vvv``
     - ``DEBUG`` (``NOTSET``)
     - + timestamps, traceback locals

You can resolve the level yourself with :func:`~xclif.level_from_verbosity`, or
read it off the dispatch context:

.. code-block:: python

   from xclif import get_context, level_from_verbosity

   get_context().verbosity     # raw count: 0–3
   get_context().log_level     # the implied logging level
   level_from_verbosity(2)     # logging.DEBUG

Integrating with Rich and the standard library
----------------------------------------------

Because Xclif only attaches a *handler* to the root logger, the two systems
compose rather than compete:

- **Any** standard-library logger flows through Rich — ``log`` is built on top
  of ``logging``, not beside it. Third-party libraries that log via ``logging``
  are rendered through the same handler.
- The handler is **lazy**: Rich is only imported the first time a record
  actually passes the level filter, keeping the startup hot path cheap.
- Output goes to **stderr**, so it never pollutes a command's stdout.

Cooperating with application-owned logging
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If your application has already configured its own handlers (for example, a
file handler set up in ``__main__``), Xclif leaves them in place and only
updates the logger level — it will not hijack your output. To force Xclif's
Rich handler to replace existing handlers, call
:func:`~xclif.configure_logging` yourself with ``force=True``:

.. code-block:: python

   from xclif import configure_logging

   configure_logging(verbosity=2, colors="never", force=True)

Manual configuration
---------------------

You rarely need to call :func:`~xclif.configure_logging` directly — Xclif
invokes it during dispatch. It is exposed for tests, scripts, and apps that
manage their own startup. Common overrides:

.. code-block:: python

   from xclif import configure_logging

   # Pin an explicit level regardless of verbosity:
   configure_logging(level="ERROR")

   # Target a specific logger instead of the root:
   configure_logging(verbosity=1, logger="myapp")

   # Force timestamps off even at -vvv:
   configure_logging(verbosity=3, show_time=False)

The ``colors`` argument mirrors the ``--colors`` flag (``"auto"``, ``"always"``,
``"never"``) so log output honors the same color preference as the rest of the
CLI.

See the :doc:`api` reference for the full signatures of
:func:`~xclif.configure_logging`, :func:`~xclif.get_logger`, and
:func:`~xclif.level_from_verbosity`.
