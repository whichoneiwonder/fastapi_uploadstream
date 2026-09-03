from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath("../src"))

project = "UploadStream"
author = "whichoneiwonder"
copyright = "2026, whichoneiwonder"

extensions = [
    "myst_parser",
    "autodoc2",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx_copybutton"
]
autodoc2_packages = [
    "../src/fastapi_uploadstream",
]
autodoc2_render_plugin = "md"
autodoc2_hidden_objects = ["private", "inherited"]

exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

source_suffix = {
    ".md": "markdown",
}

myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "fieldlist",
]

autodoc_member_order = "bysource"
autodoc_typehints = "description"

html_theme = "shibuya"
html_title = "UploadStream"
html_static_path = ["_static"]
html_css_files = ["colors.css"]
html_theme_options = {
    "accent_color": "lime",
    # Development platforms
    "github_url": "https://github.com/whichoneiwonder/fastapi_uploadstream",
    "logo_target": "https://whichoneiwonder.github.io/fastapi_uploadstream",
    "og_image_url": "https://whichoneiwonder.github.io/fastapi_uploadstream/_static/cropped-colored-logo.svg",
}
# html_logo = "_static/logo.png"
html_favicon = "_static/logo.png"

