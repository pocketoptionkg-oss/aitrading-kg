@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo  AITRADING.KG - error log setup (one time)
echo  ----------------------------------------
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\errlog_setup.ps1"
echo.
pause
