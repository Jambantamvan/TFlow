@echo off
title TFlow Hardware and Power Manager
chcp 65001 >nul

:: Request Administrator Privileges
net session >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Requesting Administrator privileges...
    powershell -Command "Start-Process -FilePath 'cmd.exe' -ArgumentList '/c \"\"%~f0\"\"' -Verb RunAs"
    exit /b
)

cd /d "%~dp0"

if exist "%~dp0target\release\tflow.exe" (
    echo Starting TFlow v2.0...
    start "" "%~dp0target\release\tflow.exe"
    exit /b
)

if exist "%~dp0tflow.exe" (
    echo Starting TFlow v2.0...
    start "" "%~dp0tflow.exe"
    exit /b
)

:: Python fallback
python --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo Starting TFlow via Python backend...
    start "" python "%~dp0main.py"
) else (
    echo Fallback: Launching AsusFanControl hardware monitor...
    "%~dp0windows_bin\PsExec.exe" -accepteula -i -s -d "%~dp0windows_bin\AsusFanControlGUI.exe"
)
