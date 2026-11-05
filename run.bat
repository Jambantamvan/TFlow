@echo off
title TFlow - ASUS Hardware and Power Manager
chcp 65001 >nul

:: Ensure working directory is the script location
cd /d "%~dp0"

:: Automatically register Windows Start Menu and Desktop shortcuts if missing
if not exist "%APPDATA%\Microsoft\Windows\Start Menu\Programs\TFlow.lnk" (
    echo Registering Start Menu shortcut for Windows Search...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws=New-Object -ComObject WScript.Shell; $s=$ws.CreateShortcut('%APPDATA%\Microsoft\Windows\Start Menu\Programs\TFlow.lnk'); $s.TargetPath='%~dp0run.bat'; $s.WorkingDirectory='%~dp0'; $s.Description='TFlow Hardware and Power Manager'; $s.Save()" 2>nul
)

if not exist "%USERPROFILE%\Desktop\TFlow.lnk" (
    echo Registering Desktop shortcut...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws=New-Object -ComObject WScript.Shell; $s=$ws.CreateShortcut('%USERPROFILE%\Desktop\TFlow.lnk'); $s.TargetPath='%~dp0run.bat'; $s.WorkingDirectory='%~dp0'; $s.Description='TFlow Hardware and Power Manager'; $s.Save()" 2>nul
)

:: Request Administrator Privileges (needed for ASUS EC and Powercfg)
net session >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Requesting Administrator privileges...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath 'cmd.exe' -ArgumentList '/c \"\"%~f0\"\"' -Verb RunAs"
    exit /b
)

:: 1. Launch standalone native compiled Rust binary if present
if exist "%~dp0target\release\tflow.exe" (
    echo Starting TFlow native core...
    start "" "%~dp0target\release\tflow.exe"
    exit /b
)

if exist "%~dp0tflow.exe" (
    echo Starting TFlow native core...
    start "" "%~dp0tflow.exe"
    exit /b
)

:: 2. Launch modernized Python TFlow GUI v2.0
python --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo Starting TFlow GUI...
    start "" pythonw "%~dp0main.py"
    if %ERRORLEVEL% NEQ 0 (
        start "" python "%~dp0main.py"
    )
    exit /b
)

:: 3. Hardware Fallback: AsusFanControl standalone GUI
echo Python not found in PATH. Launching AsusFanControl fallback...
start "" "%~dp0windows_bin\PsExec.exe" -accepteula -i -s -d "%~dp0windows_bin\AsusFanControlGUI.exe"
