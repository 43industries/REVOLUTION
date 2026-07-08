@echo off
cd /d "%~dp0"
python --version >nul 2>&1
if errorlevel 1 (
  echo Python is not installed or not in PATH.
  pause
  exit /b 1
)
echo Installing build dependencies...
python -m pip install -q -r requirements.txt
python -m pip install -q pyinstaller
echo Building REVOLUTION.exe...
python -m PyInstaller --noconfirm --onefile --windowed --name REVOLUTION ^
  --add-data "trailer.html;." ^
  --collect-all pygame ^
  revolution.py
if errorlevel 1 (
  echo Build failed.
  pause
  exit /b 1
)
copy /Y trailer.html dist\ >nul 2>&1
echo.
echo Done: dist\REVOLUTION.exe
echo Run from this folder so saves persist in revolution_save.json
pause
