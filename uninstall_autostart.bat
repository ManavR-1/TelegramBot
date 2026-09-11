@echo off
cd /d "%~dp0"
echo Removing Telegram Bot Auto-Start...
set "STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
if exist "%STARTUP_FOLDER%\TelegramPremiumBot.lnk" (
    del /f /q "%STARTUP_FOLDER%\TelegramPremiumBot.lnk"
    echo Shortcut removed from Startup folder.
)
call stop_bot.bat
echo Auto-start removed and bot stopped.
pause
