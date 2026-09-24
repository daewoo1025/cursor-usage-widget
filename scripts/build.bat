@echo off
setlocal
title Build CursorWidget.exe
cd /d "%~dp0.."

echo ===================================================
echo   Building CursorWidget.exe  (clean rebuild)
echo ===================================================
echo.

echo [1/4] Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 goto :fail

echo.
echo [2/4] Stopping any running CursorWidget.exe...
taskkill /IM CursorWidget.exe /F >nul 2>&1
ping -n 2 127.0.0.1 >nul

echo.
echo [3/4] Clearing old build outputs...
if exist "dist" rmdir /S /Q "dist"
if exist "build" rmdir /S /Q "build"
if exist "release\CursorWidget-Windows" rmdir /S /Q "release\CursorWidget-Windows"

echo.
echo [4/4] Compiling with PyInstaller...
pyinstaller --noconfirm --clean CursorWidget.spec
if errorlevel 1 goto :fail

echo.
echo ===================================================
echo SUCCESS
echo   dist\CursorWidget\CursorWidget.exe
echo.
echo Tip: run scripts\pack-release.bat 0.1.0 for a GitHub zip
echo ===================================================
if not defined CI pause
exit /b 0

:fail
echo.
echo BUILD FAILED.
echo If you saw Access Denied, close CursorWidget.exe and retry.
if not defined CI pause
exit /b 1
