Shell Completions
=================

Every Xclif CLI automatically includes a ``completions`` subcommand that prints a shell
completion script for bash, zsh, or fish.

Generating a script
-------------------

.. code-block:: bash

   myapp completions bash
   myapp completions zsh
   myapp completions fish

Installing completions
----------------------

Pipe the output to the appropriate location for your shell:

**bash**

.. code-block:: bash

   myapp completions bash > ~/.local/share/bash-completion/completions/myapp

**zsh**

.. code-block:: bash

   myapp completions zsh > ~/.zsh/completions/_myapp

**fish**

.. code-block:: bash

   myapp completions fish > ~/.config/fish/completions/myapp.fish

When ``stdout`` is a terminal, Xclif prints the install hint to ``stderr`` automatically so
you can also just run ``myapp completions bash`` and copy the suggested command.

How it works
------------

The ``completions`` subcommand is injected by :class:`~xclif.Cli` at initialisation time —
no code changes required in your app. The generated scripts complete subcommand names and
``--option`` flags at each command level.
