@echo off
setlocal

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_mobile_typer.ps1" -LaunchAfterInstall
exit /b %errorlevel%
