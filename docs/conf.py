import os
import sys
from importlib.metadata import version as installed_version
from pathlib import Path

import django

repository_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repository_root))
sys.path.insert(0, str(repository_root / "src"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.settings")
django.setup()

project = "django-outreach"
author = "Mahadi Eric"
copyright = "Mahadi Eric"
release = installed_version("django-outreach")
version = release

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
    "sphinx_copybutton",
]

source_suffix = {".md": "markdown"}
exclude_patterns = ["_build"]

myst_enable_extensions = ["colon_fence", "deflist"]

autodoc_member_order = "bysource"
autodoc_typehints = "description"
autodoc_default_options = {"show-inheritance": True}

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "django": (
        "https://docs.djangoproject.com/en/5.2/",
        "https://docs.djangoproject.com/en/5.2/_objects/",
    ),
}

html_theme = "furo"
html_title = f"django-outreach {release}"
html_static_path = ["_static"]
