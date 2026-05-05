#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# build.sh  –  Build the Galamax WASM / web bundle using pygbag
#
# Usage (from the project root):
#   bash WASM/build.sh
#
# Output:
#   WASM/build/web/        ← open index.html here in a browser
#
# Serve locally (Python 3):
#   cd WASM/build/web && python3 -m http.server 8000
#   then open  http://localhost:8000
# ---------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VENV_PYTHON="$PROJECT_ROOT/.venv/bin/python"

# Prefer the venv python if present, otherwise fall back to system python3
if [[ -x "$VENV_PYTHON" ]]; then
    PYTHON="$VENV_PYTHON"
else
    PYTHON="$(command -v python3)"
fi

echo "==> Using Python: $PYTHON"
echo "==> Building WASM bundle from: $SCRIPT_DIR"

"$PYTHON" -m pygbag \
    --app_name  "Galamax" \
    --title     "GALAMAX – Space Defender" \
    --width     800 \
    --height    600 \
    --build \
    "$SCRIPT_DIR"

# Some browsers still probe /favicon.ico even with rel=icon png.
# Mirror favicon.png to favicon.ico so local server logs stay clean.
if [[ -f "$SCRIPT_DIR/build/web/favicon.png" ]]; then
    cp "$SCRIPT_DIR/build/web/favicon.png" "$SCRIPT_DIR/build/web/favicon.ico"
fi

# pygbag 0.9.3 template emits a broken BrowserFS URL for some builds.
# Rewrite it to a known-good CDN so the page can boot reliably.
if [[ -f "$SCRIPT_DIR/build/web/index.html" ]]; then
    sed -i \
        's#https://pygame-web.github.io/cdn/0.9.3//browserfs.min.js#https://cdn.jsdelivr.net/npm/browserfs@1.4.3/dist/browserfs.min.js#g' \
        "$SCRIPT_DIR/build/web/index.html"
fi

echo ""
echo "==> Build complete!"
echo "    Files are in: $SCRIPT_DIR/build/web/"
echo ""
echo "    To serve locally run:"
echo "      cd \"$SCRIPT_DIR/build/web\" && python3 -m http.server 8000"
echo "    then open http://localhost:8000 in your browser."
