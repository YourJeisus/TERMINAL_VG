@echo off
chcp 65001 >nul 2>&1
title Terminal VG

echo [1/8] Closing Chrome...
taskkill /F /IM chrome.exe >nul 2>&1
timeout /t 2 /nobreak >nul

echo [2/8] Updating from GitHub...
cd /d "%~dp0"
git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo       Git not found. Skipping update.
) else (
    git pull origin master 2>&1
    if %errorlevel% equ 0 (
        echo       Updated successfully.
    ) else (
        echo       Update failed. Continuing with current version.
    )
)

echo [3/8] Checking Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo       Python not found. Downloading...
    set "PY_URL=https://www.python.org/ftp/python/3.12.9/python-3.12.9-amd64.exe"
    set "PY_EXE=%TEMP%\python_install.exe"
    powershell -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; (New-Object Net.WebClient).DownloadFile($env:PY_URL, $env:PY_EXE)"
    echo       Installing Python...
    "%TEMP%\python_install.exe" /quiet InstallAllUsers=1 PrependPath=1 Include_pip=1
    timeout /t 10 /nobreak >nul
    set "PATH=%PATH%;C:\Program Files\Python312;C:\Program Files\Python312\Scripts"
    echo       Done.
)

echo [4/8] Installing print libraries...
python -m pip install --quiet pywin32 Pillow >nul 2>&1

echo [5/8] Setting silent print policy...
REG ADD "HKLM\SOFTWARE\Policies\Google\Chrome" /v SilentPrintingEnabled /t REG_DWORD /d 1 /f >nul 2>&1
REG ADD "HKCU\SOFTWARE\Policies\Google\Chrome" /v SilentPrintingEnabled /t REG_DWORD /d 1 /f >nul 2>&1
REG ADD "HKLM\SOFTWARE\Policies\Google\Chrome" /v PrintPreviewUseSystemDefaultPrinter /t REG_DWORD /d 1 /f >nul 2>&1
REG ADD "HKCU\SOFTWARE\Policies\Google\Chrome" /v PrintPreviewUseSystemDefaultPrinter /t REG_DWORD /d 1 /f >nul 2>&1

echo [6/8] Starting print server (port 9999)...
cd /d "%~dp0"
start /b "" python server.py --print-only
timeout /t 1 /nobreak >nul

echo [7/8] Starting payment service (port 5050)...
start /b "" python payment_service.py
timeout /t 2 /nobreak >nul

echo [8/8] Launching Chrome kiosk...
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --user-data-dir="C:\TerminalVG" --kiosk --kiosk-printing --disable-session-crashed-bubble --noerrdialogs --disable-infobars --disable-features=TranslateUI --disable-background-mode --disable-pinch --overscroll-history-navigation=0 https://terminal-vg.vercel.app

echo.
echo === Terminal started ===
echo Print server:   localhost:9999
echo Payment service: localhost:5050 (PAX S300 via DualConnector)
echo Exit kiosk: Alt+F4
pause
