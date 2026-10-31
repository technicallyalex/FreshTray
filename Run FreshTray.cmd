@echo off
setlocal
set "FRESHTRAY_EXE=%~dp0app\FreshTray-0.2.exe"
if not exist "%FRESHTRAY_EXE%" set "FRESHTRAY_EXE=%~dp0app\FreshTray.exe"
if not exist "%FRESHTRAY_EXE%" set "FRESHTRAY_EXE=%~dp0app\FreshTray-Qt\FreshTray.exe"
if not exist "%FRESHTRAY_EXE%" set "FRESHTRAY_EXE=%~dp0app\FreshTray\FreshTray.exe"
if not exist "%FRESHTRAY_EXE%" (
  echo FreshTray.exe is missing. See README.md for build instructions.
  pause
  exit /b 1
)
start "" "%FRESHTRAY_EXE%" %*
