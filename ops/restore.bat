@echo off
rem Restore the Future Mirror AI database from a backup file.
rem   restore.bat                      (lists backups and asks which one)
rem   restore.bat fm_20261016_190000.dump
setlocal
set "FM_RC=0"
cd /d "%~dp0.."
call "%~dp0_common.bat" :checkdocker || goto fail
set "FM_FILE=%~1"
if not "%FM_FILE%"=="" goto havefile
if not exist "backups\*.dump" (
  echo No backups found in the backups folder. Run backup.bat first.
  goto fail
)
echo Available backups, newest first:
dir /b /o-d "backups\*.dump"
echo.
set /p "FM_FILE=Type the backup file name to restore: "
:havefile
if defined FM_FILE set "FM_FILE=%FM_FILE:"=%"
if not defined FM_FILE (
  echo [ERROR] No file name given.
  goto fail
)
if not exist "%FM_FILE%" if exist "backups\%FM_FILE%" set "FM_FILE=backups\%FM_FILE%"
if not exist "%FM_FILE%" (
  echo [ERROR] File not found: %FM_FILE%
  goto fail
)
echo.
echo WARNING: this replaces ALL current data with the contents of:
echo   %FM_FILE%
echo A safety backup of the current data is taken first.
set /p "FM_OK=Type YES to continue: "
if /i not "%FM_OK%"=="YES" (
  echo Cancelled. Nothing was changed.
  goto done
)
echo Taking a safety backup of the current data ...
set "FM_SAVED_NO_PAUSE=%FM_NO_PAUSE%"
set "FM_NO_PAUSE=1"
call "%~dp0backup.bat"
set "FM_BACKUP_RC=%errorlevel%"
set "FM_NO_PAUSE=%FM_SAVED_NO_PAUSE%"
if not "%FM_BACKUP_RC%"=="0" goto fail
echo Stopping the app ...
docker compose stop frontend backend || goto fail
docker compose up -d db || goto fail
call "%~dp0_common.bat" :waitdb || goto fail
echo Restoring ...
docker compose cp "%FM_FILE%" db:/tmp/fm_restore.dump || goto fail
docker compose exec -T db sh -c "dropdb -U $POSTGRES_USER --if-exists --force $POSTGRES_DB && createdb -U $POSTGRES_USER $POSTGRES_DB && pg_restore -U $POSTGRES_USER -d $POSTGRES_DB --no-owner --exit-on-error /tmp/fm_restore.dump; rc=$?; rm -f /tmp/fm_restore.dump; exit $rc" || goto fail
echo Starting the app ...
docker compose up -d || goto fail
call "%~dp0_common.bat" :waitapp || goto fail
echo Restore complete.
goto done
:fail
echo [FAILED] See the messages above. If the restore failed half-way, restore the safety backup the same way.
set "FM_RC=1"
:done
if not defined FM_NO_PAUSE pause
exit /b %FM_RC%
