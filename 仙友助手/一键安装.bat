@echo off
chcp 65001 >nul
title Xianyou Helper Installer
echo.
echo   Xianyou Helper - One-click installer
echo   Starting, please wait...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
echo.
pause
