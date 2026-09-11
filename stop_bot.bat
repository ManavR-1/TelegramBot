@echo off
setlocal
echo ============================================================
echo   Stopping Telegram Bot...
echo ============================================================
echo.

powershell -NoProfile -Command "Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.Path -like '*PremiumTelegramBot*' } | Stop-Process -Force"
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*run_bot.bat*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

echo.
echo [DONE] Telegram Bot stopped.
echo.
pause
