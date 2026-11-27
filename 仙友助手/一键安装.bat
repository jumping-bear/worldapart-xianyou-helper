@echo off
chcp 65001 >nul
title 不问凡尘 · 仙友助手 一键安装
echo.
echo   不问凡尘 · 仙友助手   一键安装
echo   正在启动安装程序，请稍候……
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
echo.
pause
