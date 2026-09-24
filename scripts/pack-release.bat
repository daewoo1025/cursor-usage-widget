@echo off
setlocal
title Pack CursorWidget Release Zip
cd /d "%~dp0.."

set VERSION=%~1
if "%VERSION%"=="" set VERSION=0.1.0

echo === Step 1/2: Clean build EXE ===
set CI=1
call "%~dp0build.bat"
if errorlevel 1 (
  echo BUILD FAILED
  pause
  exit /b 1
)

echo.
echo === Step 2/2: Create release zip ===
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0pack-release.ps1" -Version %VERSION%
if errorlevel 1 (
  echo PACK FAILED
  pause
  exit /b 1
)

echo.
echo Upload this to GitHub Releases:
echo   release\CursorWidget-Windows-v%VERSION%.zip
echo.
pause
