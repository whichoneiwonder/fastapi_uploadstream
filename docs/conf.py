from __future__ import annotations

import html
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
    "sphinx_copybutton",
    "sphinxext.opengraph",
]
autodoc2_packages = [
    "../src/fastapi_uploadstream",
]
autodoc2_render_plugin = "md"
autodoc2_hidden_objects = ["private", "inherited"]

exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

source_suffix = {
    ".md": "markdown",
    ".svg": "image/svg+xml",
}

myst_enable_extensions = ["colon_fence", "deflist", "fieldlist", "attrs_inline"]

autodoc_member_order = "bysource"
autodoc_typehints = "description"
MAIN_URL = "https://whichoneiwonder.github.io/fastapi_uploadstream"

html_theme = "shibuya"
html_title = "UploadStream"
html_static_path = ["_static"]
html_css_files = ["colors.css"]
ogp_site_url = MAIN_URL
ogp_image = f"{MAIN_URL}/_static/generated_og_logo_opt.png"
ogp_social_cards = {
    "enable": True,
    "image": f"{MAIN_URL}/_static/generated_og_logo_opt.png",
    "title": "UploadStream - FastAPI extensions for streaming file uploads",
    "line_color": "#009B00",
}

google_site_verification = os.getenv("GOOGLE_SITE_VERIFICATION")
ogp_custom_meta_tags = []
if google_site_verification:
    ogp_custom_meta_tags.append(
        f'<meta name="google-site-verification" content="{html.escape(google_site_verification, quote=True)}" />'
    )


html_theme_options = {
    "accent_color": "lime",
    # Development platforms
    "github_url": "https://github.com/whichoneiwonder/fastapi_uploadstream",
    "logo_target": MAIN_URL,
    "og_image_url": f"{MAIN_URL}/_static/logo.png",
}
# could also add html_logo = "_static/logo.png" if needed, but the logo doesn't look great when small.
html_favicon = "_static/logo.png"
