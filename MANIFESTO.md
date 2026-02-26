# The Xclif Manifesto

## CLI frameworks are good, actually

Click and Typer are excellent tools. If you're building a script with a handful of flags, they're the right choice. Decorator-based, ergonomic, and mature — there's a reason the Python ecosystem converged on them.

But CLIs have gotten more ambitious. `git`, `cargo`, `poetry`, `kubectl`, `gh` — these aren't scripts. They're structured command hierarchies, sometimes dozens of subcommands deep, each with their own arguments and options. Building something at that scale with Click or Typer reveals a different class of problem: not the API itself, but the organizational model underneath it.

Additionally, users expect DX features that used to be luxuries: beautiful help, man pages, shell completion, color toggling, configuration files, auto-discovering plugins. In other libraries, this means either installing various different plugins or gluing together code which may become easily outdated if not integrated well into your CLI.

## The problem at scale

When your CLI grows, these frameworks ask you to do the same thing a web developer did before routing frameworks existed: manually assemble the structure.

With Click you write `@cli.group()`, then `@group.command()`, then you import everything into one place and wire it up. With Typer it's similar — you create `app = typer.Typer()`, then `sub = typer.Typer()`, then `app.add_typer(sub)`. Your command tree ends up scattered across files, or collapsed into a single massive `cli.py`. The shape of your CLI and the shape of your codebase are two separate things you're responsible for keeping in sync.

This is exactly the problem web frameworks solved with routing.

## The insight from web development

When FastAPI or Next.js or Rails arrived, they didn't just give you a better API for writing handlers. They changed the organizational model: **the directory structure is the route map**. A file at `routes/users/settings.py` *is* the `/users/settings` handler. You don't register it. The framework discovers it.

That's what CLIs have been missing. Xclif brings that same insight:

```
myapp/
└── routes/
    ├── __init__.py       →  myapp
    ├── greet.py          →  myapp greet
    └── config/
        ├── __init__.py   →  myapp config
        ├── get.py        →  myapp config get
        └── set.py        →  myapp config set
```

No registration. No boilerplate assembly. Drop a file in the right folder and the command exists. A developer reading the filesystem immediately understands the CLI's surface area.

## The contract is the function

The other half is what goes *inside* those files. You write a function, annotate it, and Xclif builds the command from the signature:

```python
@command()
def _(name: str, template: str = "Hello, {}!") -> None:
    """Greet someone by name."""
    print(template.format(name))
```

`name` has no default → it's a positional argument. `template` has a default → it's a `--template` option. The docstring becomes the help text. The type annotation determines how the value is parsed. No separate `help=` strings scattered through decorator arguments. The function signature *is* the CLI contract.

Your `__main__.py` is three lines. `Cli.from_routes(routes)` and you're done.

## The Principles

**1. Structure is layout.**
The command tree mirrors the file tree. A developer reading the filesystem should immediately understand the CLI's surface area.

**2. Functions are commands.**
A command is just a Python function. Its signature is its interface.

**3. Types do the work.**
Annotations already express what a parameter is. Xclif reads them — no separate `help=` strings, no `metavar=`, no duplicate declarations.

**4. Zero boilerplate at the entry point.**
Your `__main__.py` is three lines. `Cli.from_routes(routes)` and you're done.

**5. Fast by default.**
Python CLI startup time is a real problem — Typer can add hundreds of milliseconds before your command even runs. Xclif is designed to stay lean. We don't import what we don't need.

**6. Escape hatches exist.**
The filesystem convention is the happy path, not a prison. The lower-level `Command` and `Cli` objects are always available when you need to go off-script.

## Where others stop, Xclif keeps going

There are several CLI libraries for Python: [argparse](https://docs.python.org/3/library/argparse.html), [Plac](https://plac.readthedocs.io/en/latest/), [Cleo](https://github.com/python-poetry/cleo), [Click](https://click.palletsprojects.com/), [Typer](https://typer.tiangolo.com/). Typer in particular is great — for small projects we'd still recommend it. But these tools solve the *parsing* problem. Xclif solves the *framework* problem.

The difference is analogous to Flask vs Django, or React vs Next.js. A library gives you components; a framework gives you a system. When you outgrow the library, you end up building the framework yourself — badly, one piece at a time, with none of the pieces designed to work together.

Xclif's goal is to be the integrated framework for serious Python CLIs. That means batteries included, but not batteries bloated:

- **Rich output** — beautiful help text, formatted errors, progress indicators, all built in
- **Config management** — the `WithConfig[T]` annotation lets any parameter read from a config file or environment variable, with a clear priority order: CLI flag > env var > config file > default
- **Logging** — `--verbose` / `-v` is wired up automatically; your commands get structured verbosity levels for free

These aren't afterthoughts bolted on. They're designed as part of the same system, so they compose correctly and don't fight each other.

The architecture is plugin-based under the hood — so the core stays lean, startup stays fast, and the framework stays extensible. You can swap implementations or add your own. But you shouldn't have to for the common cases.

## Fast by default

Python CLI startup time is a real problem. Typer can add hundreds of milliseconds before your command even runs — it inherits Click's import chain and layered abstractions. For a tool you invoke dozens of times a day, that latency is felt.

Xclif was written from scratch, not built on argparse or Click. The parser is custom-built for performance, not based on [getopt](https://pubs.opengroup.org/onlinepubs/9699919799/utilities/getopts.html) or any existing library — while still adhering to [POSIX guidelines](https://pubs.opengroup.org/onlinepubs/9699919799/basedefs/V1_chap12.html#tag_12_02) where possible to keep with convention. Starting from zero means we don't inherit anyone else's quirks or overhead.

## What Xclif is not for

Xclif is not the right tool for a single-command script with three flags. Click or argparse will get you there faster with less overhead. Xclif is for **structured, multi-command CLIs** — the kind where the organizational model matters and where you want the full stack working together out of the box.

## The goal

The best CLIs feel inevitable. The commands are where you expect them, the options do what you think, the help text is actually useful. Xclif's goal is to make building that kind of CLI the path of least resistance.

Ship the CLI you meant to build.
