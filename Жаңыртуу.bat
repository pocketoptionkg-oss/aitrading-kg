@echo off
chcp 65001 >nul
rem AITRADING.KG — маалыматты кол менен жаңыртуу / обновить данные вручную
rem ИИ-обзор үчүн: set ANTHROPIC_API_KEY=... (же Windows'тун чөйрө өзгөрмөсүнө кошуңуз)
cd /d "%~dp0"
python -m pip install --quiet --disable-pip-version-check -r tools\requirements.txt
python tools\update_bingx.py
python tools\ai_posts.py
echo.
echo Даяр. Эми site папкасын хостингге кайра жүктөңүз (же git push).
pause
