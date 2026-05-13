#!/usr/bin/env bash
# start-forge.sh — Start the ZDS Forge API with all required library paths.
#
# Homebrew installs glib/pango/cairo to a non-standard path that macOS's
# dynamic linker doesn't search by default. DYLD_LIBRARY_PATH bridges the gap
# so weasyprint can find libgobject-2.0 for PDF generation.
#
# Usage:
#   ./start-forge.sh              # default port 8001
#   PORT=8002 ./start-forge.sh   # custom port
#   ./start-forge.sh --reload    # hot-reload for dev

set -euo pipefail

PORT="${PORT:-8001}"
BREW_LIB="$(brew --prefix)/lib"

export DYLD_LIBRARY_PATH="${BREW_LIB}:${DYLD_LIBRARY_PATH:-}"

echo "▶  Starting ZDS Forge API on port ${PORT}"
echo "   DYLD_LIBRARY_PATH=${DYLD_LIBRARY_PATH}"

exec uvicorn apps.zds.api.main:app --port "${PORT}" "$@"
