import os
import sys

sys.path.insert(0, os.path.abspath("../src"))

project = "Xclif"
copyright = "2024, Bryan Hu"
author = "Bryan Hu"
release = "0.1.0"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "myst_parser",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store", "option-system-design.md"]

html_theme = "furo"
html_static_path = ["_static"]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

autodoc_member_order = "bysource"
autodoc_typehints = "description"

myst_enable_extensions = ["colon_fence"]
