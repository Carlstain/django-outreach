#!/usr/bin/env bash
set -euo pipefail

locale_directory=src/outreach/locale/fr/LC_MESSAGES
compiled_copy="$(mktemp)"
trap 'rm -f "$compiled_copy"' EXIT

pybabel compile --input-file "$locale_directory/django.po" --output-file "$compiled_copy" --locale fr
if ! cmp --silent "$compiled_copy" "$locale_directory/django.mo"; then
  echo "django.mo is not the compiled django.po, run scripts/compile_messages.sh" >&2
  exit 1
fi
