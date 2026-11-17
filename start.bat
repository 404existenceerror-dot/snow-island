@echo off
rem Snow Island launcher: sets things up on the first run, then starts the app.
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" goto run

echo First start: setting up Snow Island. This downloads the libraries once (about 100 MB).

set "PY="
py -3 --version >nul 2>&1 && set "PY=py -3"
if not defined PY python --version >nul 2>&1 && set "PY=python"
if not defined PY goto nopython

%PY% -m venv .venv
if errorlevel 1 goto nopython
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto failed

:run
start "" ".venv\Scripts\pythonw.exe" "%~dp0snow_island.py"
exit /b 0

:nopython
echo.
echo Python 3.10 or newer is needed.
echo Get it from https://www.python.org/downloads/ and tick "Add python.exe to PATH" while installing.
echo Then run start.bat again.
if exist ".venv" rmdir /s /q ".venv"
pause
exit /b 1

:failed
echo.
echo Setup failed. Check your internet connection (only needed for this first setup) and try again.
if exist ".venv" rmdir /s /q ".venv"
pause
exit /b 1
