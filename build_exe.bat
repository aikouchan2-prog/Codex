@echo off
setlocal enabledelayedexpansion

REM Build a Windows executable with PyInstaller

if not exist .venv (
  python -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt pyinstaller

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist ImageSorter.spec del /q ImageSorter.spec

pyinstaller --name ImageSorter --onefile --windowed app.py

if not exist dist\ImageSorter.exe (
  echo [ERROR] Build failed: dist\ImageSorter.exe not found.
  exit /b 1
)

echo Build complete: dist\ImageSorter.exe
echo.
echo Next: run package_release.bat to create a shareable ZIP.
endlocal
