@echo off
title TUF Control Center (Windows)
chcp 65001 >nul

:: Meminta Administrator Privileges otomatis
net session >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Meminta izin Administrator...
    powershell -Command "Start-Process -FilePath 'cmd.exe' -ArgumentList '/c \"\"%~f0\"\"' -Verb RunAs"
    exit /b
)

cd /d "%~dp0"

:: Cek apakah Python terpasang di Windows
python --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo Membuka antarmuka TUF Control Center...
    start "" python "%~dp0main.py"
) else (
    echo Python tidak terdeteksi di Windows PATH.
    echo Menjalankan fallback AsusFanControl GUI bawaan...
    "%~dp0windows_bin\PsExec.exe" -accepteula -i -s -d "%~dp0windows_bin\AsusFanControlGUI.exe"
)

