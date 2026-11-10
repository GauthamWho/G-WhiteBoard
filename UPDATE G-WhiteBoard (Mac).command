#!/bin/bash
# UPDATE G-WhiteBoard (Mac) - double-click me when the board shows
# "Update available". Downloads the newest version and rebuilds it.
# Your board data is NOT touched (it is not part of git).

cd "$(cd "$(dirname "$0")" && pwd)" || exit 1

echo
echo " Updating G-WhiteBoard ..."
echo

git pull || { echo "Could not reach GitHub - check your internet and try again."; exit 1; }

.venv/bin/python -m pip install -q -r watcher/requirements.txt

( cd web && npm install --silent >/dev/null 2>&1 && npm run build >/dev/null 2>&1 )

echo
echo " Done! Close this window, then restart G-WhiteBoard"
echo " (double-click START G-WhiteBoard (Mac).command)."
