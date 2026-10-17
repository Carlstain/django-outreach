#!/usr/bin/env bash
set -euo pipefail

compiled_copy="$(mktemp)"
trap 'rm -f "$compiled_copy"' EXIT

for locale in fr es pt pt_BR; do
  locale_directory="src/outreach/locale/$locale/LC_MESSAGES"
  pybabel compile --input-file "$locale_directory/django.po" --output-file "$compiled_copy" --locale "$locale"
  if ! cmp --silent "$compiled_copy" "$locale_directory/django.mo"; then
    echo "$locale_directory/django.mo is not the compiled django.po, run scripts/compile_messages.sh" >&2
    exit 1
  fi
done
