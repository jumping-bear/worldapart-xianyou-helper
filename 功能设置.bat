@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist "仙友助手.exe" (
    "仙友助手.exe" --settings
) else (
    python touch_progress.py --settings
)
pause
