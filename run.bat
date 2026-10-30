@echo off
rem Project Atlas: double-click to scan this computer and open the overview page.
setlocal
cd /d "%~dp0"
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
  where python >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo Python 3.9+ was not found. Install it from https://www.python.org/downloads/ ^(tick "Add python.exe to PATH"^), then run this again.
  pause
  exit /b 1
)
%PY% -m project_atlas --open %*
if errorlevel 1 (
  echo.
  echo The scan stopped with an error, see the messages above.
  pause
  exit /b 1
)
endlocal
