#!/bin/bash
# start_mac.command — launch the Whiteboard Catcher watcher (macOS)
#
# !!! IMPORTANT — READ BEFORE FIRST RUN !!!
# macOS will ask for ACCESSIBILITY permission for the global hotkey
# (default: Fn+Cmd+C) to work: System Settings -> Privacy & Security -> Accessibility,
# then allow Terminal (or the app running this script).
# This script and the macOS capture path have NOT been tested on a Mac yet —
# if something fails, check watcher.log in this folder.

# Resolve the folder this script lives in
DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$DIR")"
VENV="$PROJECT_ROOT/.venv"

# 1. Venv
if [ ! -f "$VENV/bin/python" ]; then
    echo "Creating venv at $VENV ..."
    python3 -m venv "$VENV"
fi

# 2. Dependencies (quiet)
"$VENV/bin/python" -m pip install -q -r "$DIR/requirements.txt"

# 3. Open the board in Microsoft Edge (falls back to default browser), then start
open -a "Microsoft Edge" http://localhost:8765 || open http://localhost:8765
cd "$DIR"
exec "$VENV/bin/python" server.py
