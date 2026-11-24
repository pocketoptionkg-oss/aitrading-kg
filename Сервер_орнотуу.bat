@echo off
chcp 65001 <nul >nul
rem AITRADING.KG — Telegram-ботту серверге орнотуу / установка бота на сервер (Ubuntu 22.04/24.04)
rem Керек: сервердин IP дареги жана root сырсөзү (сервер сатып алганда берилет).
echo.
echo  AITRADING.KG — ботту серверге орнотуу
echo  ------------------------------------------
set /p IP=Сервердин IP дареги (мисалы 95.217.10.20): 
if "%IP%"=="" goto :eof
echo.
echo  1/2 Орнотуучуну серверге жиберебиз. Биринчи жолу "yes" деп жазып, анан root сырсөзүн киргизиңиз (экранда көрүнбөйт).
"%SystemRoot%\System32\OpenSSH\scp.exe" "%~dp0deploy\server\install.sh" root@%IP%:/root/install.sh
if errorlevel 1 (echo. & echo  ! Жиберилген жок. IP жана сырсөздү текшериңиз. & pause & goto :eof)
echo.
echo  2/2 Орнотуу башталды. Сырсөздү дагы бир жолу киргизиңиз. Андан кийин экрандагы кадамдарды аткарыңыз.
"%SystemRoot%\System32\OpenSSH\ssh.exe" -t root@%IP% "bash /root/install.sh"
echo.
pause
