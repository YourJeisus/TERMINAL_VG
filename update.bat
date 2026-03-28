@echo off
chcp 65001 >nul 2>&1
title Terminal VG — Update

cd /d "%~dp0"
set "REPO_ZIP=%TEMP%\terminal_vg_update.zip"
set "REPO_EXTRACT=%TEMP%\terminal_vg_update"

echo.
echo  Updating Terminal VG from GitHub...
echo.

git --version >nul 2>&1
if %errorlevel% equ 0 (
    echo  [git] Pulling latest changes...
    git pull origin master 2>&1
    if %errorlevel% equ 0 (
        echo.
        echo  Updated successfully.
        goto :done
    ) else (
        echo  [git] Pull failed. Trying ZIP download...
    )
)

echo  Downloading ZIP from GitHub...
powershell -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; try { Invoke-WebRequest -Uri 'https://github.com/YourJeisus/TERMINAL_VG/archive/refs/heads/master.zip' -OutFile $env:REPO_ZIP -UseBasicParsing -TimeoutSec 30; Write-Host ' Download OK' } catch { Write-Host ' Download FAILED'; exit 1 }"
if %errorlevel% neq 0 (
    echo.
    echo  Update failed. Check internet connection.
    goto :done
)

echo  Extracting...
if exist "%REPO_EXTRACT%" rmdir /s /q "%REPO_EXTRACT%" >nul 2>&1
powershell -Command "Expand-Archive -Path $env:REPO_ZIP -DestinationPath $env:REPO_EXTRACT -Force"
if exist "%REPO_EXTRACT%\TERMINAL_VG-master\" (
    xcopy /s /y /q "%REPO_EXTRACT%\TERMINAL_VG-master\*" "%~dp0" >nul 2>&1
    echo.
    echo  Updated successfully.
) else (
    echo.
    echo  Extract failed.
)

if exist "%REPO_ZIP%" del /q "%REPO_ZIP%" >nul 2>&1
if exist "%REPO_EXTRACT%" rmdir /s /q "%REPO_EXTRACT%" >nul 2>&1

:done
echo.
pause
