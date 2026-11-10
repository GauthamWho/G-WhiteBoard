#!/bin/bash
# OPEN G-WhiteBoard (Mac) - double-click to reopen the board window
# The server must already be running (started with START G-WhiteBoard (Mac).command)

if curl -s --max-time 2 http://localhost:8765 > /dev/null 2>&1; then
  open http://localhost:8765
else
  osascript -e 'display dialog "G-WhiteBoard server is not running.\n\nStart it first with:\nSTART G-WhiteBoard (Mac).command" buttons {"OK"} default button "OK"'
fi
