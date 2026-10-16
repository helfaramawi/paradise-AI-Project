@echo off
rem Start Future Mirror AI (builds the images on first run) and open it in the browser.
setlocal
set "FM_RC=0"
if /i "%~1"=="/nopause" set "FM_NO_PAUSE=1"
cd /d "%~dp0.."
call "%~dp0_common.bat" :checkdocker || goto fail
echo Starting Future Mirror AI ...
docker compose up -d || goto fail
call "%~dp0_common.bat" :waitapp || goto fail
start "" "http://localhost:%FM_PORT%"
goto done
:fail
echo [FAILED] See the messages above.
set "FM_RC=1"
:done
if not defined FM_NO_PAUSE pause
exit /b %FM_RC%
