#!/bin/sh
set -eu

cd "$(dirname "$0")/.."
for locale in fr es pt pt_BR; do
  pybabel compile -d src/outreach/locale -D django -l "$locale"
done
