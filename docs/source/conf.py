"""Configuration Sphinx pour android-save."""

import os
import sys

sys.path.insert(0, os.path.abspath("../../src"))

project = "android-save"
author = "Laurent"
release = "0.1.0"
copyright = "2026, Laurent"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
    "sphinx.ext.napoleon",
    "sphinx_autodoc_typehints",
]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "textual": ("https://textual.textualize.io", None),
}

autosummary_generate = True
autodoc_default_options = {
    "show-inheritance": True,
    "special-members": "__init__",
}
autodoc_inherit_docstrings = False
autodoc_typehints = "description"
napoleon_google_docstring = False
napoleon_numpy_docstring = False

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
templates_path = ["_templates"]
exclude_patterns = []

language = "fr"
