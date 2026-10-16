@echo off
rem Stop Future Mirror AI. Your data is kept (the database volume is not deleted).
setlocal
set "FM_RC=0"
if /i "%~1"=="/nopause" set "FM_NO_PAUSE=1"
cd /d "%~dp0.."
call "%~dp0_common.bat" :checkdocker || goto fail
echo Stopping Future Mirror AI ...
docker compose --profile automation down || goto fail
echo Stopped. Your data is kept. Run start.bat to start again.
goto done
:fail
echo [FAILED] See the messages above.
set "FM_RC=1"
:done
if not defined FM_NO_PAUSE pause
exit /b %FM_RC%
