@echo off
cd /d "%~dp0RevolutionGodot"
set "GODOT="
where godot >nul 2>&1 && set "GODOT=godot"
if not defined GODOT if exist "%LOCALAPPDATA%\Microsoft\WinGet\Packages\GodotEngine.GodotEngine_Microsoft.Winget.Source_8wekyb3d8bbwe\Godot_v4.7.2-stable_win64.exe" set "GODOT=%LOCALAPPDATA%\Microsoft\WinGet\Packages\GodotEngine.GodotEngine_Microsoft.Winget.Source_8wekyb3d8bbwe\Godot_v4.7.2-stable_win64.exe"
if not defined GODOT (
  echo Godot 4 not found. Install with: winget install GodotEngine.GodotEngine
  pause
  exit /b 1
)
"%GODOT%" --path "%cd%" --rendering-method gl_compatibility
if errorlevel 1 pause
