@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

python print_message.py --dry-run --no-rotate --save-preview preview.png
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Preview generation failed.
    echo.
    pause
    exit /b 1
)

if exist preview.png start "" "%~dp0preview.png"

echo.
pause
