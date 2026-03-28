@echo off
chcp 65001 >nul 2>&1
title Terminal VG — Update
cd /d "%~dp0"

set "REPO_URL=https://github.com/YourJeisus/TERMINAL_VG"
set "REPO_ZIP=%TEMP%\terminal_vg_update.zip"
set "REPO_EXTRACT=%TEMP%\terminal_vg_update"

echo.
echo  ========================================
echo    Terminal VG — Update
echo  ========================================
echo.

:: -----------------------------------------------
:: 1. Check / Install Git
:: -----------------------------------------------
git --version >nul 2>&1
if %errorlevel% equ 0 (
    echo  [OK] Git found.
    goto :git_ready
)

echo  [!] Git not installed. Installing...
winget --version >nul 2>&1
if %errorlevel% equ 0 (
    echo       Installing via winget...
    winget install --id Git.Git -e --silent --accept-package-agreements --accept-source-agreements
    timeout /t 5 /nobreak >nul
    set "PATH=%PATH%;C:\Program Files\Git\cmd"
    git --version >nul 2>&1
    if %errorlevel% equ 0 (
        echo  [OK] Git installed.
        goto :git_ready
    )
)

echo       winget unavailable. Downloading Git installer...
set "GIT_EXE=%TEMP%\git_install.exe"
powershell -Command "$ProgressPreference='SilentlyContinue'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://github.com/git-for-windows/git/releases/download/v2.47.1.windows.2/Git-2.47.1.2-64-bit.exe' -OutFile $env:GIT_EXE -UseBasicParsing"
if exist "%GIT_EXE%" (
    echo       Installing Git...
    "%GIT_EXE%" /VERYSILENT /NORESTART /NOCANCEL /SP- /CLOSEAPPLICATIONS /RESTARTAPPLICATIONS
    timeout /t 5 /nobreak >nul
    set "PATH=%PATH%;C:\Program Files\Git\cmd"
    if exist "%GIT_EXE%" del /q "%GIT_EXE%" >nul 2>&1
    git --version >nul 2>&1
    if %errorlevel% equ 0 (
        echo  [OK] Git installed.
        goto :git_ready
    )
)
echo  [!] Git install failed. Will use ZIP fallback.
goto :zip_update

:: -----------------------------------------------
:: 2. Git clone or pull
:: -----------------------------------------------
:git_ready
if exist "%~dp0.git\" (
    echo.
    echo  Pulling latest changes...
    git pull origin master 2>&1
    if %errorlevel% equ 0 (
        echo  [OK] Updated via git pull.
        goto :check_python
    ) else (
        echo  [!] Git pull failed. Resetting...
        git fetch origin master 2>&1
        git reset --hard origin/master 2>&1
        if %errorlevel% equ 0 (
            echo  [OK] Updated via git reset.
            goto :check_python
        )
        echo  [!] Git reset failed. Trying ZIP...
        goto :zip_update
    )
) else (
    echo.
    echo  First run — cloning repository...
    git clone %REPO_URL%.git "%~dp0_clone_tmp" 2>&1
    if %errorlevel% equ 0 (
        xcopy /s /y /q "%~dp0_clone_tmp\*" "%~dp0" >nul 2>&1
        rmdir /s /q "%~dp0_clone_tmp" >nul 2>&1
        echo  [OK] Repository cloned.
        goto :check_python
    ) else (
        if exist "%~dp0_clone_tmp" rmdir /s /q "%~dp0_clone_tmp" >nul 2>&1
        echo  [!] Clone failed. Trying ZIP...
        goto :zip_update
    )
)

:: -----------------------------------------------
:: 3. ZIP fallback (with fast download)
:: -----------------------------------------------
:zip_update
echo.
echo  Downloading ZIP from GitHub...
powershell -Command "$ProgressPreference='SilentlyContinue'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; try { Invoke-WebRequest -Uri '%REPO_URL%/archive/refs/heads/master.zip' -OutFile $env:REPO_ZIP -UseBasicParsing; Write-Host '  [OK] Downloaded' } catch { Write-Host '  [FAIL]'; exit 1 }"
if %errorlevel% neq 0 (
    echo  Update failed. Check internet connection.
    goto :check_python
)
echo  Extracting...
if exist "%REPO_EXTRACT%" rmdir /s /q "%REPO_EXTRACT%" >nul 2>&1
powershell -Command "$ProgressPreference='SilentlyContinue'; Expand-Archive -Path $env:REPO_ZIP -DestinationPath $env:REPO_EXTRACT -Force"
if exist "%REPO_EXTRACT%\TERMINAL_VG-master\" (
    xcopy /s /y /q "%REPO_EXTRACT%\TERMINAL_VG-master\*" "%~dp0" >nul 2>&1
    echo  [OK] Updated from ZIP.
) else (
    echo  [!] Extract failed.
)
if exist "%REPO_ZIP%" del /q "%REPO_ZIP%" >nul 2>&1
if exist "%REPO_EXTRACT%" rmdir /s /q "%REPO_EXTRACT%" >nul 2>&1

:: -----------------------------------------------
:: 4. Check / Install Python
:: -----------------------------------------------
:check_python
echo.
python --version >nul 2>&1
if %errorlevel% equ 0 (
    echo  [OK] Python found.
    goto :check_pip
)

echo  [!] Python not installed. Installing...
winget --version >nul 2>&1
if %errorlevel% equ 0 (
    echo       Installing via winget...
    winget install --id Python.Python.3.12 -e --silent --accept-package-agreements --accept-source-agreements
    timeout /t 10 /nobreak >nul
    set "PATH=%PATH%;C:\Program Files\Python312;C:\Program Files\Python312\Scripts"
    python --version >nul 2>&1
    if %errorlevel% equ 0 (
        echo  [OK] Python installed.
        goto :check_pip
    )
)

echo       Downloading Python installer...
set "PY_URL=https://www.python.org/ftp/python/3.12.9/python-3.12.9-amd64.exe"
set "PY_EXE=%TEMP%\python_install.exe"
powershell -Command "$ProgressPreference='SilentlyContinue'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%PY_URL%' -OutFile $env:PY_EXE -UseBasicParsing"
if exist "%PY_EXE%" (
    echo       Installing Python...
    "%PY_EXE%" /quiet InstallAllUsers=1 PrependPath=1 Include_pip=1
    timeout /t 10 /nobreak >nul
    set "PATH=%PATH%;C:\Program Files\Python312;C:\Program Files\Python312\Scripts"
    if exist "%PY_EXE%" del /q "%PY_EXE%" >nul 2>&1
    echo  [OK] Python installed.
) else (
    echo  [!] Python install failed.
)

:: -----------------------------------------------
:: 5. Install pip dependencies
:: -----------------------------------------------
:check_pip
python -m pip install --quiet pywin32 Pillow >nul 2>&1
echo  [OK] Python libraries ready.

echo.
echo  ========================================
echo    Update complete!
echo  ========================================
echo.
pause
