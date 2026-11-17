@echo off
rem Start HAQQ and open it in the browser. Rebuilds the images when the code has changed (e.g. after git pull).
rem First run: creates .env from .env.example (edit HAQQ_SECRET_KEY and HAQQ_DB_PASSWORD before real use).
setlocal
set "HQ_RC=0"
if /i "%~1"=="/nopause" set "HQ_NO_PAUSE=1"
cd /d "%~dp0.."
call "%~dp0_common.bat" :checkdocker || goto fail
if not exist ".env" (
  copy /y ".env.example" ".env" >nul && echo Created .env from .env.example - review it before real use.
)
echo Starting HAQQ ...
docker compose up -d --build || goto fail
call "%~dp0_common.bat" :waitapp || goto fail
start "" "http://localhost:%HQ_PORT%"
goto done
:fail
echo [FAILED] See the messages above.
set "HQ_RC=1"
:done
if not defined HQ_NO_PAUSE pause
exit /b %HQ_RC%
