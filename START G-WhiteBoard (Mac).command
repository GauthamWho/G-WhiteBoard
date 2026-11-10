#!/bin/bash
# START G-WhiteBoard (Mac) - double-click me.
# Starts the watcher (listens for Fn+Cmd+C) and opens your board
# in the browser. Keep the small terminal window open while you work.

DIR="$(cd "$(dirname "$0")" && pwd)"
exec bash "$DIR/watcher/start_mac.command"
