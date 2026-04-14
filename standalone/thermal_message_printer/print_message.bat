@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

python print_message.py %*
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Print failed.
)

echo.
pause
