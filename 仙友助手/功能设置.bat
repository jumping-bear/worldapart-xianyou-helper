@echo off
chcp 936 >nul
cd /d "%~dp0"
if exist "оисяжЗйж.exe" (
    "оисяжЗйж.exe" --settings
) else (
    python xianyou_assistant.py --settings
)
pause
