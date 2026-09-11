@echo off
setlocal
cd /d "%~dp0"
if not exist "%~dp0logs" mkdir "%~dp0logs"

:loop
echo [%date% %time%] Starting Telegram Bot... >> "%~dp0logs\bot.log"
"%~dp0.venv\Scripts\python.exe" -u "%~dp0app.py" >> "%~dp0logs\bot.log" 2>&1
echo [%date% %time%] Bot exited with code %errorlevel%. Restarting in 5 seconds... >> "%~dp0logs\bot.log"
ping 127.0.0.1 -n 6 >nul
goto loop
