@echo off
cd /d "%~dp0"
title Nova Launcher
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 nova.py
) else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo Python 3.10 or newer is not installed.
    echo Download it from https://www.python.org/downloads/ and tick "Add python.exe to PATH" in the installer.
  ) else (
    python nova.py
  )
)
echo.
echo Nova has stopped. If there is an error above, send it to whoever gave you Nova.
pause
