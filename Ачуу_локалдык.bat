@echo off
chcp 65001 >nul
rem AITRADING.KG — сайтты компьютерде ачуу / открыть сайт на компьютере
cd /d "%~dp0site"
start "AITRADING.KG server" python -m http.server 8765 --bind 127.0.0.1
timeout /t 2 >nul
start "" http://localhost:8765/
