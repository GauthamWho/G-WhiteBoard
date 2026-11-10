@echo off
rem UPDATE G-WhiteBoard (Windows) - double-click me when the board shows
rem "Update available". Downloads the newest version and rebuilds it.
rem Your board data is NOT touched (it is not part of git).

title Update G-WhiteBoard
cd /d "%~dp0"

echo.
echo  Updating G-WhiteBoard ...
echo.

git pull || (echo Could not reach GitHub - check your internet and try again. & pause & exit /b 1)

.venv\Scripts\python.exe -m pip install -q -r watcher\requirements.txt

cd web
call npm install --silent >nul 2>&1
call npm run build >nul 2>&1
cd ..

echo.
echo  Done! Close this window, then restart G-WhiteBoard
echo  (double-click START G-WhiteBoard (Windows).bat).
echo.
pause
