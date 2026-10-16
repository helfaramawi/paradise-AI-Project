@echo off
rem Restart Future Mirror AI (stop, then start), rebuilding if the code changed. Use after editing .env or pulling.
setlocal
set "FM_RC=0"
if /i "%~1"=="/nopause" set "FM_NO_PAUSE=1"
cd /d "%~dp0.."
call "%~dp0_common.bat" :checkdocker || goto fail
echo Restarting Future Mirror AI ...
docker compose down || goto fail
docker compose up -d --build || goto fail
call "%~dp0_common.bat" :waitapp || goto fail
goto done
:fail
echo [FAILED] See the messages above.
set "FM_RC=1"
:done
if not defined FM_NO_PAUSE pause
exit /b %FM_RC%
