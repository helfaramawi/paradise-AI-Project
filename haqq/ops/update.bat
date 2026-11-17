@echo off
rem Update HAQQ: verified backup, pull the latest code from GitHub, rebuild and restart (migrations run automatically).
setlocal
set "HQ_RC=0"
if /i "%~1"=="/nopause" set "HQ_NO_PAUSE=1"
cd /d "%~dp0.."
call "%~dp0_common.bat" :checkdocker || goto fail
echo Step 1/3: taking a full, verified backup ...
set "HQ_SAVED_NO_PAUSE=%HQ_NO_PAUSE%"
set "HQ_NO_PAUSE=1"
call "%~dp0backup.bat"
set "HQ_BACKUP_RC=%errorlevel%"
set "HQ_NO_PAUSE=%HQ_SAVED_NO_PAUSE%"
if not "%HQ_BACKUP_RC%"=="0" goto fail
echo Step 2/3: pulling the latest code ...
git pull origin main || goto fail
echo Step 3/3: rebuilding and restarting ...
docker compose up -d --build || goto fail
call "%~dp0_common.bat" :waitapp || goto fail
echo Update complete.
goto done
:fail
echo [FAILED] See the messages above. Your data is safe in the backup just taken.
set "HQ_RC=1"
:done
if not defined HQ_NO_PAUSE pause
exit /b %HQ_RC%
