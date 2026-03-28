@echo off
chcp 65001 >nul 2>&1
title Terminal VG

echo [1/8] Closing Chrome...
taskkill /F /IM chrome.exe >nul 2>&1
timeout /t 2 /nobreak >nul

echo [2/8] Updating from GitHub...
cd /d "%~dp0"
set "REPO_ZIP=%TEMP%\terminal_vg_update.zip"
set "REPO_EXTRACT=%TEMP%\terminal_vg_update"
git --version >nul 2>&1
if %errorlevel% equ 0 (
    git pull origin master 2>&1
    if %errorlevel% equ 0 (
        echo       Updated via git.
    ) else (
        echo       Git pull failed. Trying ZIP download...
        goto :zip_update
    )
    goto :update_done
)
:zip_update
echo       Downloading latest version...
powershell -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; try { Invoke-WebRequest -Uri 'https://github.com/YourJeisus/TERMINAL_VG/archive/refs/heads/master.zip' -OutFile $env:REPO_ZIP -UseBasicParsing -TimeoutSec 30; Write-Host 'OK' } catch { Write-Host 'FAIL'; exit 1 }"
if %errorlevel% neq 0 (
    echo       Download failed. Continuing with current version.
    goto :update_done
)
echo       Extracting...
if exist "%REPO_EXTRACT%" rmdir /s /q "%REPO_EXTRACT%" >nul 2>&1
powershell -Command "Expand-Archive -Path $env:REPO_ZIP -DestinationPath $env:REPO_EXTRACT -Force"
if exist "%REPO_EXTRACT%\TERMINAL_VG-master\" (
    xcopy /s /y /q "%REPO_EXTRACT%\TERMINAL_VG-master\*" "%~dp0" >nul 2>&1
    echo       Updated successfully.
) else (
    echo       Extract failed. Continuing with current version.
)
if exist "%REPO_ZIP%" del /q "%REPO_ZIP%" >nul 2>&1
if exist "%REPO_EXTRACT%" rmdir /s /q "%REPO_EXTRACT%" >nul 2>&1
:update_done

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
