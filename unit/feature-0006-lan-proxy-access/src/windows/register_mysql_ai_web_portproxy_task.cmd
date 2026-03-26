@echo off
setlocal
pushd "%~dp0" || exit /b 1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\register_mysql_ai_web_portproxy_task.ps1" %*
set "exit_code=%errorlevel%"
popd
exit /b %exit_code%
