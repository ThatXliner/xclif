# Poetry clone

A [Poetry](https://python-poetry.org/) (1.7.1) clone via Xclif — delegates to the real `poetry` binary as a subprocess.

Demonstrates nested subcommands (`self show plugins`, `env use`, etc.) using the file-system routing convention.

## Commands

| Command | Description |
|---|---|
| `poetry env use <python>` | Activate/create a virtualenv for a Python version |
| `poetry self update [--preview]` | Update Poetry to the latest version |
| `poetry self show plugins` | List installed Poetry plugins |

## Usage

```
python -m poetry env use 3.11
python -m poetry self update
python -m poetry self update --preview
python -m poetry self show plugins
```
