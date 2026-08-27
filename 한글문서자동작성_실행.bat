@echo off
chcp 65001 >nul
set SCRIPT=%~dp0한글문서자동작성.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%SCRIPT%"
