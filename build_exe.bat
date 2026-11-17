@echo off
rem Builds dist\SnowIsland.exe (a single file people can download and run, no Python needed).
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run start.bat once first so the libraries get installed.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q pyinstaller
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name SnowIsland --icon assets\icon.ico ^
  --collect-submodules winrt ^
  snow_island.py
if errorlevel 1 goto failed
echo.
echo Done: dist\SnowIsland.exe
pause
exit /b 0

:failed
echo Build failed.
pause
exit /b 1
