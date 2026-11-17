@echo off
rem Restore HAQQ from a backup made by backup.bat.
rem   restore.bat                          (lists backups and asks which one)
rem   restore.bat haqq_20261118_090000     (a backup folder in haqq\backups, or a full path)
rem Restores the database and all stored documents. .env is restored only if this machine has none
rem (an existing .env is kept; the backed-up one is saved next to it as .env.from-backup).
rem A safety backup of the current data is taken first. After the restore every stored file is re-checked.
setlocal
set "HQ_RC=0"
cd /d "%~dp0.."
call "%~dp0_common.bat" :checkdocker || goto fail
set "HQ_SRC=%~1"
if not "%HQ_SRC%"=="" goto havesrc
dir /b /ad "backups\haqq_*" >nul 2>&1 || goto nobackups
echo Available backups, newest first:
dir /b /ad /o-n "backups\haqq_*"
echo.
set /p "HQ_SRC=Type the backup name to restore: "
:havesrc
if defined HQ_SRC set "HQ_SRC=%HQ_SRC:"=%"
if not defined HQ_SRC (
  echo [ERROR] No backup name given.
  goto fail
)
if not exist "%HQ_SRC%\" if exist "backups\%HQ_SRC%\" set "HQ_SRC=backups\%HQ_SRC%"
if not exist "%HQ_SRC%\" goto notfound
if not exist "%HQ_SRC%\database.dump" goto nodump
if not exist "%HQ_SRC%\documents.tar.gz" goto nodocs
for %%i in ("%HQ_SRC%") do set "HQ_SRC_ABS=%%~fi"
echo.
if exist "%HQ_SRC%\manifest.txt" findstr /b /c:"Created:" /c:"Code version:" /c:"Database:" /c:"Documents:" "%HQ_SRC%\manifest.txt"
echo.
echo WARNING: this replaces ALL current HAQQ data (database and documents) with the contents of:
echo   %HQ_SRC%
echo A safety backup of the current data is taken first (when HAQQ is running).
set /p "HQ_OK=Type YES to continue: "
if /i not "%HQ_OK%"=="YES" (
  echo Cancelled. Nothing was changed.
  goto done
)

rem Configuration first: on a new machine the database must start with the backed-up password.
if not exist "%HQ_SRC%\env.backup" goto safety
if exist ".env" goto compareenv
copy /y "%HQ_SRC%\env.backup" ".env" >nul || goto fail
echo Restored .env from the backup.
goto safety
:compareenv
fc /b ".env" "%HQ_SRC%\env.backup" >nul 2>&1 && goto safety
copy /y "%HQ_SRC%\env.backup" ".env.from-backup" >nul
echo Kept your current .env; the backed-up one is saved as .env.from-backup - compare them if logins fail.

:safety
docker compose ps --status running --services 2>nul | findstr /b /l "backend" >nul || goto stopapp
echo Taking a safety backup of the current data ...
set "HQ_SAVED_NO_PAUSE=%HQ_NO_PAUSE%"
set "HQ_NO_PAUSE=1"
call "%~dp0backup.bat"
set "HQ_BACKUP_RC=%errorlevel%"
set "HQ_NO_PAUSE=%HQ_SAVED_NO_PAUSE%"
if not "%HQ_BACKUP_RC%"=="0" goto fail

:stopapp
echo 1/4 Stopping HAQQ ...
docker compose stop frontend worker backend >nul 2>&1
docker compose up -d db || goto fail
call "%~dp0_common.bat" :waitdb || goto fail
echo 2/4 Restoring the database ...
docker compose cp "ops\db\haqq_db.sh" db:/tmp/haqq_db.sh >nul 2>&1 || goto fail
docker compose cp "%HQ_SRC%\database.dump" db:/tmp/haqq_restore.dump >nul 2>&1 || goto fail
docker compose exec -T db sh /tmp/haqq_db.sh restore /tmp/haqq_restore.dump || goto fail
docker compose exec -T db rm -f /tmp/haqq_restore.dump /tmp/haqq_db.sh >nul 2>&1
echo 3/4 Restoring documents ...
docker compose run --rm --no-deps -v "%HQ_SRC_ABS%:/in:ro" --entrypoint sh backend -c "rm -rf /data/storage/* && tar xzf /in/documents.tar.gz -C /data" || goto fail

echo 4/4 Starting HAQQ and checking every stored file ...
docker compose up -d || goto fail
call "%~dp0_common.bat" :waitapp || goto fail
docker compose exec -T backend python -m app.ops_tools check-storage || goto fail
docker compose exec -T backend python -m app.ops_tools counts
echo Restore complete.
goto done

:nobackups
echo No backups found in haqq\backups. Run ops\backup.bat first.
goto fail
:notfound
echo [ERROR] Backup not found: %HQ_SRC%
goto fail
:nodump
echo [ERROR] No database.dump in %HQ_SRC%
goto fail
:nodocs
echo [ERROR] No documents.tar.gz in %HQ_SRC%
goto fail
:fail
echo [FAILED] See the messages above. If the restore stopped half-way, restore the safety backup the same way.
set "HQ_RC=1"
:done
if not defined HQ_NO_PAUSE pause
exit /b %HQ_RC%
