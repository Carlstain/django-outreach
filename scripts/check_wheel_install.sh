#!/usr/bin/env bash
set -euo pipefail

repository_root="$(pwd)"
wheel_path="$(realpath "$(ls -t dist/django_outreach-*.whl | head -n 1)")"
work_directory="$(mktemp -d)"
trap 'rm -rf "$work_directory"' EXIT

cp tests/settings/wheel.py "$work_directory/settings_wheel.py"
cp tests/urls/wheel.py "$work_directory/urls_wheel.py"

uv venv --quiet "$work_directory/venv"
uv pip install --quiet --python "$work_directory/venv/bin/python" "$wheel_path"

cd "$work_directory"
env PYTHONPATH="$work_directory" REPOSITORY_ROOT="$repository_root" \
  "$work_directory/venv/bin/python" - <<'PYTHON'
import os
import sys
from pathlib import Path

import outreach

installed_root = Path(outreach.__file__).parent
source_root = Path(os.environ["REPOSITORY_ROOT"]) / "src" / "outreach"
expected = [
    path.relative_to(source_root)
    for path in source_root.rglob("*")
    if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
]
missing = [str(path) for path in expected if not (installed_root / path).is_file()]
required = [
    Path("locale/fr/LC_MESSAGES/django.mo"),
    Path("THIRD_PARTY_NOTICES.md"),
    Path("templates/outreach/admin/emailtemplate_form.html"),
    Path("templates/outreach/admin/emailtemplate_list.html"),
]
missing += [str(path) for path in required if not (installed_root / path).is_file()]
if missing:
    sys.exit(f"missing from the installed package: {sorted(set(missing))}")
print(f"{len(expected)} files verified in {installed_root}")
PYTHON

env PYTHONPATH="$work_directory" DJANGO_SETTINGS_MODULE=settings_wheel \
  "$work_directory/venv/bin/django-admin" check
env PYTHONPATH="$work_directory" DJANGO_SETTINGS_MODULE=settings_wheel \
  "$work_directory/venv/bin/django-admin" collectstatic --noinput
