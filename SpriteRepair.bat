@echo off
setlocal
cd /d "%~dp0"
title Sprite Repair
echo.
echo === Sprite Repair ===
echo UI: http://127.0.0.1:5190/
echo.

set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY where python >nul 2>&1 && set "PY=python"
if not defined PY (
  echo [ERROR] Python not found. Install Python 3.11+ and retry.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating .venv ...
  %PY% -m venv .venv
  if errorlevel 1 (
    echo [ERROR] venv failed
    pause
    exit /b 1
  )
)

set "VPY=.venv\Scripts\python.exe"
"%VPY%" -c "import PIL" 1>nul 2>nul
if errorlevel 1 (
  echo Installing Pillow ...
  "%VPY%" -m pip install --disable-pip-version-check -q pillow
  if errorlevel 1 (
    echo [ERROR] pip install pillow failed
    pause
    exit /b 1
  )
)

REM If already listening on 5190, just open browser
netstat -ano | findstr ":5190" | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
  echo Server already running on 5190.
  start "" "http://127.0.0.1:5190/"
  echo.
  pause
  exit /b 0
)

echo Starting server on port 5190 ...
start "SpriteRepairServer" /D "%~dp0" "%VPY%" server.py
timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:5190/"
echo.
echo Browser opened. Close the SpriteRepairServer window to stop.
echo.
pause
