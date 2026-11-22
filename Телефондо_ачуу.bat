@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
rem AITRADING.KG — сайтты телефондо ачуу (ошол эле Wi-Fi аркылуу) + QR-код / открыть сайт на телефоне
cd /d "%~dp0"
python tools\phone_qr.py
pause
