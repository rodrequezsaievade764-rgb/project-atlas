#!/usr/bin/env sh
# Project Atlas: scan this computer and open the overview page.
cd "$(dirname "$0")" || exit 1
if command -v python3 >/dev/null 2>&1; then PY=python3
elif command -v python >/dev/null 2>&1; then PY=python
else echo "Python 3.9+ was not found: https://www.python.org/downloads/"; exit 1
fi
exec "$PY" -m project_atlas --open "$@"
