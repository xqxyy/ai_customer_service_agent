@echo off
setlocal

cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_project.ps1" %*

echo.
echo If startup succeeded, use the browser workbench to test the project.
pause
