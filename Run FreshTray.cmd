@echo off
setlocal
if not exist "%~dp0app\FreshTray\FreshTray.exe" (
  echo FreshTray.exe is missing. See README.md for build instructions.
  pause
  exit /b 1
)
start "" "%~dp0app\FreshTray\FreshTray.exe" %*
