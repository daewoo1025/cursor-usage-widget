@echo off
setlocal
title Cursor Pro+ Widget
cd /d "%~dp0.."

echo Installing dependencies...
pip install -r requirements.txt
echo.
echo Starting from source...
python src\CursorWidget.py
if errorlevel 1 (
  echo.
  echo Launch failed. Need Python 3.13+ on PATH.
  pause
)
