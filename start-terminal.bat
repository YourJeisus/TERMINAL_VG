@echo off
chcp 65001 >nul 2>&1
title Terminal VG

echo [1/5] Closing Chrome...
taskkill /F /IM chrome.exe >nul 2>&1
timeout /t 2 /nobreak >nul

echo [2/5] Checking Python...
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

echo [3/5] Installing print libraries...
python -m pip install --quiet pywin32 Pillow >nul 2>&1

echo [4/5] Setting silent print policy...
REG ADD "HKLM\SOFTWARE\Policies\Google\Chrome" /v SilentPrintingEnabled /t REG_DWORD /d 1 /f >nul 2>&1
REG ADD "HKCU\SOFTWARE\Policies\Google\Chrome" /v SilentPrintingEnabled /t REG_DWORD /d 1 /f >nul 2>&1
REG ADD "HKLM\SOFTWARE\Policies\Google\Chrome" /v PrintPreviewUseSystemDefaultPrinter /t REG_DWORD /d 1 /f >nul 2>&1
REG ADD "HKCU\SOFTWARE\Policies\Google\Chrome" /v PrintPreviewUseSystemDefaultPrinter /t REG_DWORD /d 1 /f >nul 2>&1

echo [5/5] Starting print server and Chrome...
cd /d "%~dp0"
start /b "" python server.py --print-only
timeout /t 2 /nobreak >nul

start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --user-data-dir="C:\TerminalVG" --kiosk --kiosk-printing --disable-session-crashed-bubble --noerrdialogs --disable-infobars --disable-features=TranslateUI --disable-background-mode --disable-pinch --overscroll-history-navigation=0 https://terminal-vg.vercel.app

echo.
echo === Terminal started ===
echo Exit kiosk: Alt+F4
pause
