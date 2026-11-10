@echo off
rem START G-WhiteBoard (Windows) - double-click me.
rem Starts the watcher (the thing that listens for Ctrl+Shift+C)
rem and opens your board in the browser. Minimise this black
rem window while you work - closing it stops the shortcut.

title G-WhiteBoard
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0watcher\start_windows.ps1"
pause
