@echo off
chcp 65001 <nul >nul
rem AITRADING.KG — Telegram-бот: меню бөлүмдөрү, брокерде катталуу, ID текшерүү, ADMIN PANEL, ⭐ сигналдар.
rem Терезе ачык турганда иштейт (компьютер уктабайт). Токтотуу: Ctrl+C же терезени жабуу.
rem Токен жана ачкычтар кодго ЖАЗЫЛБАЙТ — Телеграм_бот_туташтыруу.bat аркылуу Windows'ко сакталат.
rem Экспирацияларды өзгөртүү: set TG_EXP=1,5    Сигналдарсыз (меню/админка гана): python tools\tg_bot.py --no-signals
cd /d "%~dp0"
python tools\tg_bot.py
pause