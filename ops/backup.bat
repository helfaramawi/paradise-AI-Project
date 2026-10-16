@echo off
rem Back up the Future Mirror AI database to backups\fm_YYYYMMDD_HHMMSS.dump
setlocal
set "FM_RC=0"
if /i "%~1"=="/nopause" set "FM_NO_PAUSE=1"
cd /d "%~dp0.."
call "%~dp0_common.bat" :checkdocker || goto fail
if not exist "backups" mkdir "backups"
docker compose up -d db || goto fail
call "%~dp0_common.bat" :waitdb || goto fail
call "%~dp0_common.bat" :timestamp
set "FM_FILE=backups\fm_%FM_TS%.dump"
echo Backing up the database ...
docker compose exec -T db sh -c "pg_dump -U $POSTGRES_USER -d $POSTGRES_DB -Fc -f /tmp/fm_backup.dump" || goto fail
docker compose cp db:/tmp/fm_backup.dump "%FM_FILE%" || goto fail
docker compose exec -T db rm -f /tmp/fm_backup.dump >nul 2>&1
for %%f in ("%FM_FILE%") do echo Backup saved: %%~ff [%%~zf bytes]
goto done
:fail
echo [FAILED] See the messages above.
set "FM_RC=1"
:done
if not defined FM_NO_PAUSE pause
exit /b %FM_RC%
