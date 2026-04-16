@echo off
setlocal

powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_windows.ps1" %*
exit /b %errorlevel%
