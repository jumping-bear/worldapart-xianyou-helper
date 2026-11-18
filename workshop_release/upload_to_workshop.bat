@echo off
chcp 936 >nul
title Steam Workshop Uploader
echo ============================================
echo   SteamCMD Workshop Uploader
echo ============================================
echo.
set /p ACC=Steam account: 
echo.
echo Logging in and uploading, enter password and Steam Guard when asked...
echo.
cd /d "%USERPROFILE%\steamcmd"
steamcmd.exe +login %ACC% +workshop_build_item "%~dp0workshop.vdf" +quit
echo.
echo ============================================
echo If upload succeeded, the item ID is printed above.
echo Fill it into workshop.vdf as publishedfileid for later updates.
echo ============================================
pause
