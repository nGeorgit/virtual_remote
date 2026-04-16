@echo off
setlocal

powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_mobile_typer.ps1" -SourcePath "%~dp0mobile-typer" -LaunchAfterInstall %*
exit /b %errorlevel%
