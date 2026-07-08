@echo off
cd /d "%~dp0"
python --version >nul 2>&1
if errorlevel 1 (
  echo Python is not installed or not in PATH.
  echo Install Python from https://www.python.org/downloads/ and try again.
  pause
  exit /b 1
)
python -m pip install -q -r requirements.txt
python revolution.py
if errorlevel 1 pause
