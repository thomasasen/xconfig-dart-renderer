#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
echo "xConfig Dart Renderer"
echo "Preparing source and generated dart assets..."
python3 scripts/restore_source_bundle.py
python3 scripts/author_assets.py
python3 scripts/web_player_assets.py
python3 scripts/build_catalog.py
echo "Browser: http://localhost:4173/"
echo "For fully local Three.js: npm install"
python3 -m http.server 4173
