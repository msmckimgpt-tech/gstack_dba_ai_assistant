@echo off
setlocal
pushd "%~dp0" || exit /b 1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\sync_mysql_ai_web_portproxy.ps1" %*
set "exit_code=%errorlevel%"
popd
exit /b %exit_code%
