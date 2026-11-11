@echo off
cd /d "%~dp0"
where pyw >nul 2>nul
if %errorlevel%==0 (
  rem pyw runs Python without a console window; errors go to nova.log in Nova's data folder.
  start "" pyw -3 nova.py
  exit /b
)
where pythonw >nul 2>nul
if %errorlevel%==0 (
  start "" pythonw nova.py
  exit /b
)
echo Python 3.10 or newer is not installed.
echo Download it from https://www.python.org/downloads/ and tick "Add python.exe to PATH" in the installer.
echo Or skip Python entirely and use Nova.exe from the Releases page.
echo.
pause
