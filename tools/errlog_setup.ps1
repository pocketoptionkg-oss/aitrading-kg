# AITRADING.KG — ката журналынын ачкычы (бир жолу). Ката_журналы_туташтыруу.bat иштетет.
# Кокус ачкыч: ушул компьютерге (ERRLOG_READ_KEY, колдонуучунун чөйрөсү) + Cloudflare Pages сыры. Экранга чыкпайт.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
$b = New-Object byte[] 32
[Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b)
$k = ([Convert]::ToBase64String($b) -replace '[+/=]', '').Substring(0, 40)
[Environment]::SetEnvironmentVariable('ERRLOG_READ_KEY', $k, 'User')
Write-Host " 1/2 Ачкыч компьютерге сакталды / ключ сохранён на компьютере" -ForegroundColor Green
$k | npx --yes wrangler pages secret put ERRLOG_READ_KEY --project-name aitrading-kg
if ($LASTEXITCODE -eq 0) {
    Write-Host " 2/2 Cloudflare'ге жазылды / записан в Cloudflare" -ForegroundColor Green
    Write-Host ""
    Write-Host " Даяр! / Готово!" -ForegroundColor Green
} else {
    Write-Host " Cloudflare'ге жазылган жок: 'npx wrangler login' менен кириңиз да, кайра иштетиңиз." -ForegroundColor Red
}
