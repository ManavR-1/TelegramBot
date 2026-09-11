@echo off
setlocal
cd /d "%~dp0"
echo ============================================================
echo   Installing Telegram Bot Auto-Start (Windows Startup)
echo ============================================================
echo.

set "STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SHORTCUT_PATH=%STARTUP_FOLDER%\TelegramPremiumBot.lnk"
set "TARGET_VBS=%~dp0start_bot_silent.vbs"
set "WORK_DIR=%~dp0"

powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT_PATH%'); $s.TargetPath = 'wscript.exe'; $s.Arguments = '\"%TARGET_VBS%\"'; $s.WorkingDirectory = '%WORK_DIR%'; $s.Save()"

if exist "%SHORTCUT_PATH%" (
    echo [SUCCESS] Auto-start shortcut created in Startup folder:
    echo %SHORTCUT_PATH%
    echo.
    echo Starting the bot silently in the background now...
    wscript.exe "%TARGET_VBS%"
    echo.
    echo The bot is now running in the background!
    echo Logs will be written to: logs\bot.log
) else (
    echo [ERROR] Failed to create shortcut in Startup folder.
)
echo.
pause
