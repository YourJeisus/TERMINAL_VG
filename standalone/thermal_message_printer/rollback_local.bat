@echo off
chcp 65001 >nul 2>&1
set "TARGET=%~dp0"
set "CLEANER=%TEMP%\vg_remove_thermal_message_printer_%RANDOM%.bat"

> "%CLEANER%" echo @echo off
>> "%CLEANER%" echo timeout /t 1 /nobreak ^>nul
>> "%CLEANER%" echo rmdir /s /q "%TARGET%"
>> "%CLEANER%" echo del /q "%%~f0"

echo Removing temporary thermal printer folder...
start "" /min cmd /c "%CLEANER%"
exit /b 0
