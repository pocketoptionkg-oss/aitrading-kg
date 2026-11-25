@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo  AITRADING.KG — ката журналын туташтыруу / подключение журнала ошибок (бир жолу)
echo  ------------------------------------------------------------------------
echo  1) Кокус ачкыч түзүлөт жана ушул компьютерге сакталат (ERRLOG_READ_KEY).
echo  2) Ошол эле ачкыч Cloudflare'ге (aitrading-kg) жашыруун түрдө жазылат.
echo  Ачкыч экранга чыкпайт.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$b = New-Object byte[] 32; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b);" ^
  "$k = ([Convert]::ToBase64String($b) -replace '[+/=]','').Substring(0,40);" ^
  "[Environment]::SetEnvironmentVariable('ERRLOG_READ_KEY', $k, 'User');" ^
  "$k | npx --yes wrangler pages secret put ERRLOG_READ_KEY --project-name aitrading-kg;" ^
  "if ($LASTEXITCODE -eq 0) { Write-Host ''; Write-Host ' Даяр! Ачкыч сакталды. / Готово!' -ForegroundColor Green } else { Write-Host ' Ката: wrangler — Cloudflare''ге кириңиз (npx wrangler login) жана кайра иштетиңиз.' -ForegroundColor Red }"
echo.
pause
