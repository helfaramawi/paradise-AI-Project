@echo off
rem Stop HAQQ. Data is kept (Docker volumes haqq_pgdata and haqq_storage).
setlocal
cd /d "%~dp0.."
docker compose stop
echo HAQQ stopped. Your data is kept. Start again with ops\start.bat
if /i not "%~1"=="/nopause" pause
