@echo off
title Build TFlow (Native Rust + Slint for Windows)
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================================
echo   TFlow v2.0 - Native Rust Windows Builder
echo ============================================================
echo.

where cargo >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Rust / Cargo is not found in your Windows PATH.
    echo Please install Rust from https://rustup.rs/ to compile tflow.exe.
    echo.
    pause
    exit /b 1
)

echo Compiling TFlow optimized release binary...
cargo build --release

if exist "target\release\tflow.exe" (
    echo.
    echo [SUCCESS] Binary compiled successfully: target\release\tflow.exe
    copy /y "target\release\tflow.exe" "tflow.exe" >nul
    echo Copied to: %~dp0tflow.exe
    echo.
    echo Registering Windows Start Menu and Desktop shortcuts...
    call "%~dp0run.bat"
) else (
    echo.
    echo [ERROR] Build failed. Please check the compiler output above.
)

pause

