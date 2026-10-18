@echo off
rem Restore Future Mirror AI from a backup made by backup.bat.
rem   restore.bat                          (lists backups and asks which one)
rem   restore.bat fm_20261018_090000       (a full backup folder)
rem   restore.bat fm_20261016_190000.dump  (an older database-only backup)
rem Restores the database, n8n data if present, and .env if this machine has none yet
rem (an existing .env is kept; the backed-up one is saved next to it as .env.from-backup).
setlocal
set "FM_RC=0"
cd /d "%~dp0.."
call "%~dp0_common.bat" :checkdocker || goto fail
set "FM_SRC=%~1"
if not "%FM_SRC%"=="" goto havesrc
dir /b "backups\fm_*" >nul 2>&1 || goto nobackups
echo Available backups, newest first:
dir /b /o-n "backups\fm_*"
echo.
set /p "FM_SRC=Type the backup name to restore: "
:havesrc
if defined FM_SRC set "FM_SRC=%FM_SRC:"=%"
if not defined FM_SRC (
  echo [ERROR] No backup name given.
  goto fail
)
if not exist "%FM_SRC%" if exist "backups\%FM_SRC%" set "FM_SRC=backups\%FM_SRC%"
if not exist "%FM_SRC%" goto notfound
set "FM_BUNDLE="
if exist "%FM_SRC%\" set "FM_BUNDLE=1"
set "FM_DUMP=%FM_SRC%"
if defined FM_BUNDLE set "FM_DUMP=%FM_SRC%\database.dump"
if not exist "%FM_DUMP%" goto nodump
for %%i in ("%FM_SRC%") do set "FM_SRC_ABS=%%~fi"
echo.
if defined FM_BUNDLE if exist "%FM_SRC%\manifest.txt" findstr /b /c:"Created:" /c:"Code version:" /c:"Verification:" "%FM_SRC%\manifest.txt"
echo WARNING: this replaces ALL current data with the contents of:
echo   %FM_SRC%
echo A safety backup of the current data is taken first (when the app has data).
set /p "FM_OK=Type YES to continue: "
if /i not "%FM_OK%"=="YES" (
  echo Cancelled. Nothing was changed.
  goto done
)

rem Configuration first: on a new machine the database must start with the backed-up password.
if not defined FM_BUNDLE goto safety
if not exist "%FM_SRC%\env.backup" goto safety
if exist ".env" goto compareenv
copy /y "%FM_SRC%\env.backup" ".env" >nul || goto fail
echo Restored .env from the backup.
goto safety
:compareenv
fc /b ".env" "%FM_SRC%\env.backup" >nul 2>&1 && goto safety
copy /y "%FM_SRC%\env.backup" ".env.from-backup" >nul
echo Kept your current .env; the backed-up one is saved as .env.from-backup - compare them if logins or connectors fail.

:safety
docker compose ps --status running --services 2>nul | findstr /b /l "backend" >nul || goto stopapp
echo Taking a safety backup of the current data ...
set "FM_SAVED_NO_PAUSE=%FM_NO_PAUSE%"
set "FM_NO_PAUSE=1"
call "%~dp0backup.bat"
set "FM_BACKUP_RC=%errorlevel%"
set "FM_NO_PAUSE=%FM_SAVED_NO_PAUSE%"
if not "%FM_BACKUP_RC%"=="0" goto fail

:stopapp
echo Stopping the app ...
docker compose --profile automation stop frontend backend n8n >nul 2>&1
docker compose up -d db || goto fail
call "%~dp0_common.bat" :waitdb || goto fail
echo Restoring the database ...
docker compose cp "ops\db\fm_db.sh" db:/tmp/fm_db.sh >nul 2>&1 || goto fail
docker compose cp "%FM_DUMP%" db:/tmp/fm_restore.dump >nul 2>&1 || goto fail
docker compose exec -T db sh /tmp/fm_db.sh restore /tmp/fm_restore.dump || goto fail
docker compose exec -T db rm -f /tmp/fm_restore.dump /tmp/fm_db.sh >nul 2>&1

if not defined FM_BUNDLE goto startapp
if not exist "%FM_SRC%\n8n.tar.gz" goto startapp
echo Restoring n8n data ...
docker volume create future-mirror_n8ndata >nul || goto fail
docker run --rm -v future-mirror_n8ndata:/data -v "%FM_SRC_ABS%:/in:ro" alpine:3.20 sh -c "rm -rf /data/* /data/.[!.]* 2>/dev/null; tar xzf /in/n8n.tar.gz -C /data" || goto fail

:startapp
echo Starting the app ...
docker compose up -d || goto fail
call "%~dp0_common.bat" :waitapp || goto fail
echo Restore complete.
goto done

:nobackups
echo No backups found in the backups folder. Run backup.bat first.
goto fail
:notfound
echo [ERROR] Backup not found: %FM_SRC%
goto fail
:nodump
echo [ERROR] No database.dump in %FM_SRC%
goto fail
:fail
echo [FAILED] See the messages above. If the restore failed half-way, restore the safety backup the same way.
set "FM_RC=1"
:done
if not defined FM_NO_PAUSE pause
exit /b %FM_RC%
