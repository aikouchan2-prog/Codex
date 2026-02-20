@echo off
setlocal

REM Create a shareable release ZIP containing ImageSorter.exe and README

if not exist dist\ImageSorter.exe (
  echo [INFO] dist\ImageSorter.exe not found. Building first...
  call build_exe.bat
  if errorlevel 1 exit /b 1
)

if not exist release mkdir release
copy /Y dist\ImageSorter.exe release\ImageSorter.exe >nul
copy /Y README.md release\README.md >nul

powershell -NoProfile -Command "Compress-Archive -Path 'release\ImageSorter.exe','release\README.md' -DestinationPath 'release\ImageSorter_release.zip' -Force"
if errorlevel 1 (
  echo [ERROR] ZIP creation failed.
  exit /b 1
)

echo Release package created: release\ImageSorter_release.zip
endlocal
