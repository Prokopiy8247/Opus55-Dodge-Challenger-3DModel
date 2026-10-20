@echo off
rem Hellcat Sandbox - Windows launcher. Double-click this one file.
rem First start: downloads the game (about 80 MB) into %USERPROFILE%\HellcatSandbox, then starts it.
setlocal
title Hellcat Sandbox
set "REPO=Prokopiy8247/Opus55-Dodge-Challenger-3DModel"
set "GAME=%USERPROFILE%\HellcatSandbox"
set "EXE=%GAME%\HellcatSandbox.exe"

rem A build made from the source (Builds\HellcatSandbox) next to this file wins
if exist "%~dp0Builds\HellcatSandbox\HellcatSandbox.exe" set "EXE=%~dp0Builds\HellcatSandbox\HellcatSandbox.exe" & goto run

if exist "%EXE%" goto run
echo.
echo  HELLCAT SANDBOX - first start
echo  Downloading the game (about 80 MB). Please wait, this happens only once...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; $ProgressPreference='SilentlyContinue'; $zip=Join-Path $env:TEMP 'HellcatSandbox-Windows.zip'; Invoke-WebRequest -UseBasicParsing -Uri 'https://github.com/%REPO%/releases/latest/download/HellcatSandbox-Windows.zip' -OutFile $zip; Expand-Archive -Force -Path $zip -DestinationPath '%GAME%'; Remove-Item $zip"
if errorlevel 1 (
  echo.
  echo  Download failed. Check your internet connection and double-click this file again.
  pause
  exit /b 1
)

:run
echo  Starting the game... (Esc inside the game opens the menu)
start "" "%EXE%"
exit /b 0
