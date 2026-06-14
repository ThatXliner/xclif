Logging
=======

Xclif wires Python's standard :mod:`logging` to its built-in ``-v`` /
``--verbose`` flag. You write ordinary log calls; Xclif decides which records
are shown and renders them with `Rich <https://rich.readthedocs.io/>`_.

.. note::

   Xclif's logging is **not a separate logging system** — it is a thin
   convenience layer over Python's standard :mod:`logging`. ``log`` forwards to
   ``logging.getLogger``, ``configure_logging`` attaches a handler to the
   ordinary root logger, and every record flows through the normal ``logging``
   tree. Anything you already know about the standard library — levels,
   handlers, filters, propagation, ``logging.getLogger(__name__)`` — applies
   unchanged. Xclif only adds the verbosity mapping, a Rich handler, and a
   couple of ergonomic helpers on top.

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
``%``-style arguments as the standard library. For a more modern, brace-style
API see :ref:`modern-style logging <modern-logging>` below.

It is not a logger of its own: on each call it resolves the **calling module's**
``__name__`` and forwards to ``logging.getLogger(<that module>)``. So records
carry the right source name and ``file:line`` no matter which module imported
``log``, and everything still flows through the standard :mod:`logging` tree.

.. _modern-logging:

Modern-style logging
~~~~~~~~~~~~~~~~~~~~~

The standard library's ``%``-style placeholders date back to 2003, before
``str.format`` (Python 2.6) and long before f-strings (3.6) existed — the
``logging`` API was simply built around the only formatting Python had at the
time. An advantage of this approach over f-strings is that string formatting
becomes lazy: the message is only interpolated if the record
clears the active level, so a filtered-out ``log.debug("%s", value)`` costs
nothing to format.

.. code-block:: python

   log.info("connecting to %s on port %d", host, port)   # stdlib, lazy

But because ``str.format`` exists now, if you prefer modern brace formatting,
``log`` offers ``f``-prefixed variants —
``fdebug``, ``finfo``, ``fwarning``, ``ferror``, ``fcritical``, ``fexception``,
and ``flog``. They take ``str.format`` (``{}`` / ``{name}``)
placeholders and, as a bonus, **call any callable argument**. Both the formatting
and the call are deferred until the record is actually emitted:

.. code-block:: python

   log.finfo("connecting to {} on port {}", host, port)
   log.fdebug("state: {}", expensive_dump)            # called only at -vv
   log.fdebug("state: {}", lambda: obj.to_json())     # lambda, same deal
   log.finfo("{user} from {host}", user=u, host=get_host)

The callable support solves a problem ``%``-style cannot: ``%`` defers the
*formatting* but not the *arguments*, so ``log.debug("%s", expensive_dump())``
runs ``expensive_dump()`` every time, even when filtered out.

With the ``f``-variants you pass the callable itself (``expensive_dump``) — never
its result (``expensive_dump()``) — and it is invoked only when needed. To log a
callable's own repr, stringify it at the call site: ``log.fdebug("fn is {}", repr(fn))``.

The same functions are available as :data:`~xclif.f` for code that prefers a
free function over the ``log`` object — ``f.debug(...)`` is exactly
``log.fdebug(...)``:

.. code-block:: python

   from xclif import f

   f.debug("state: {}", expensive_dump)

.. tip::

   f-strings work too — ``log.info(f"port {port}")`` — but they format
   **eagerly**, every time the line runs, even when the message is discarded.
   The f-variants keep brace syntax *and* stay lazy.

When to use which
+++++++++++++++++

- ``log.info`` / ``log.debug`` / ... — the default. Byte-for-byte compatible
  with the standard library, so existing code and ``logging`` linters keep
  working. Reach for these unless you have a reason not to.
- ``log.finfo`` / ``log.fdebug`` / ... — when you want brace formatting, or when
  an argument is expensive to compute and should only run if the record is
  emitted.

Skipping the ergonomic layer
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You do not have to use ``log`` or ``f`` at all. If you prefer plain standard
loggers — for an explicitly named logger, a per-component level, or simply to
avoid Xclif-specific imports — just use :func:`logging.getLogger` directly:

.. code-block:: python

   import logging
   logger = logging.getLogger(__name__)   # the standard way

   logger.info("Connecting to %s...", target)
   logger.debug("Resolving %s...", target)

This still gets Xclif's verbosity level and Rich rendering for free: your named
logger propagates up to the **root** logger, which is where
:func:`~xclif.configure_logging` sets the level and installs the handler. There
is no extra wiring to do.

``get_logger`` is a thin convenience wrapper for readers who would rather import
everything from ``xclif``; it returns the exact same standard logger:

.. code-block:: python

   from xclif import get_logger
   logger = get_logger(__name__)          # identical to logging.getLogger

.. note::

   This is also the path with the least overhead. The ``log`` object inspects
   the call stack on every call (via ``sys._getframe``) to recover the calling
   module's name and keep ``file:line`` accurate — the cost of being a single
   shared object. A logger you name yourself with ``getLogger(__name__)``
   already knows its module, so it skips that work entirely.

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
