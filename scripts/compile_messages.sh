#!/bin/sh
set -eu

cd "$(dirname "$0")/.."
pybabel compile -d src/outreach/locale -D django -l fr
