@echo off
rem Update to the latest version: back up, pull the latest code from GitHub, rebuild and restart.
setlocal
set "FM_RC=0"
if /i "%~1"=="/nopause" set "FM_NO_PAUSE=1"
cd /d "%~dp0.."
call "%~dp0_common.bat" :checkdocker || goto fail
echo Step 1/3: backing up the database ...
set "FM_SAVED_NO_PAUSE=%FM_NO_PAUSE%"
set "FM_NO_PAUSE=1"
call "%~dp0backup.bat"
set "FM_BACKUP_RC=%errorlevel%"
set "FM_NO_PAUSE=%FM_SAVED_NO_PAUSE%"
if not "%FM_BACKUP_RC%"=="0" goto fail
echo Step 2/3: pulling the latest code ...
git pull origin main || goto fail
echo Step 3/3: rebuilding and restarting ...
docker compose up -d --build || goto fail
call "%~dp0_common.bat" :waitapp || goto fail
echo Update complete.
goto done
:fail
echo [FAILED] See the messages above.
set "FM_RC=1"
:done
if not defined FM_NO_PAUSE pause
exit /b %FM_RC%
