@echo off
rem Full, verified backup of Future Mirror AI into backups\fm_YYYYMMDD_HHMMSS\ :
rem   database.dump  all application data (PostgreSQL custom-format dump)
rem   env.backup     the .env file (database password, connector secrets) - keep backups private
rem   n8n.tar.gz     n8n workflows and settings (only if the automation profile was ever used)
rem   project.tar.gz the project folder: code and git history, local changes, docs, demo videos, music
rem                  (not node_modules or older backups - those are rebuilt or already kept)
rem   manifest.txt   time, code version, verification result, row counts, SHA-256 checksums
rem Every backup is test-restored into a scratch database and compared with the live data.
rem Options (environment or .env): FM_BACKUP_KEEP=30 (newest backups kept), FM_BACKUP_COPY_TO=D:\Backups (second copy),
rem FM_BACKUP_FILES=0 (leave out the project folder).
setlocal
set "FM_RC=0"
set "FM_DIR="
if /i "%~1"=="/nopause" set "FM_NO_PAUSE=1"
cd /d "%~dp0.."
call "%~dp0_common.bat" :checkdocker || goto fail

set "FM_KEEP=%FM_BACKUP_KEEP%"
set "FM_COPY_TO=%FM_BACKUP_COPY_TO%"
set "FM_FILES=%FM_BACKUP_FILES%"
if exist ".env" if not defined FM_KEEP for /f "tokens=1,* delims==" %%a in ('findstr /b /c:"FM_BACKUP_KEEP=" ".env"') do set "FM_KEEP=%%b"
if exist ".env" if not defined FM_COPY_TO for /f "tokens=1,* delims==" %%a in ('findstr /b /c:"FM_BACKUP_COPY_TO=" ".env"') do set "FM_COPY_TO=%%b"
if exist ".env" if not defined FM_FILES for /f "tokens=1,* delims==" %%a in ('findstr /b /c:"FM_BACKUP_FILES=" ".env"') do set "FM_FILES=%%b"
if not defined FM_KEEP set "FM_KEEP=30"
set /a FM_KEEP=FM_KEEP+0 2>nul
if %FM_KEEP% lss 1 set "FM_KEEP=30"

call "%~dp0_common.bat" :timestamp
set "FM_NAME=fm_%FM_TS%"
set "FM_DIR=backups\%FM_NAME%"
mkdir "%FM_DIR%" || goto fail
docker compose up -d db || goto fail
call "%~dp0_common.bat" :waitdb || goto fail
docker compose cp "ops\db\fm_db.sh" db:/tmp/fm_db.sh >nul 2>&1 || goto fail

echo 1/5 Backing up the database ...
docker compose exec -T db sh /tmp/fm_db.sh backup /tmp/fm_backup.dump || goto fail
docker compose cp db:/tmp/fm_backup.dump "%FM_DIR%\database.dump" >nul 2>&1 || goto fail

echo 2/5 Verifying the backup by restoring it into a scratch database ...
docker compose exec -T db sh /tmp/fm_db.sh verify /tmp/fm_backup.dump > "%FM_DIR%\verify.txt"
if errorlevel 1 (
  type "%FM_DIR%\verify.txt"
  echo [ERROR] Backup verification failed - this backup is NOT usable.
  goto fail
)
set "FM_VERDICT="
for /f "usebackq delims=" %%v in ("%FM_DIR%\verify.txt") do if not defined FM_VERDICT set "FM_VERDICT=%%v"
del "%FM_DIR%\verify.txt"
echo     %FM_VERDICT%
docker compose exec -T db cat /tmp/fm_restored_counts.txt > "%FM_DIR%\counts.txt" || goto fail
docker compose exec -T db rm -f /tmp/fm_backup.dump /tmp/fm_db.sh /tmp/fm_live_counts.txt /tmp/fm_restored_counts.txt /tmp/fm_verify.log >nul 2>&1

echo 3/5 Saving configuration and automation data ...
if exist ".env" (
  copy /y ".env" "%FM_DIR%\env.backup" >nul || goto fail
  echo     .env saved
) else (
  echo     no .env file - defaults in use
)
docker volume inspect future-mirror_n8ndata >nul 2>&1 || goto non8n
docker run --rm -v future-mirror_n8ndata:/data:ro -v "%CD%\%FM_DIR%:/out" alpine:3.20 tar czf /out/n8n.tar.gz -C /data . || goto fail
echo     n8n data saved
goto files
:non8n
echo     n8n not used - nothing to save
:files
echo 4/5 Saving the project folder (code, docs, videos) ...
set "FM_FILES_NOTE=not included (FM_BACKUP_FILES=0)"
if "%FM_FILES%"=="0" goto filesdone
docker run --rm -v "%CD%:/src:ro" -v "%CD%\%FM_DIR%:/out" alpine:3.20 sh -c "cd /src && tar czf /out/project.tar.gz --exclude=./backups --exclude=node_modules --exclude=__pycache__ --exclude=./.venv --exclude=./frontend/dist --exclude=.pytest_cache --exclude=.ruff_cache --exclude=./frontend/test-results --exclude=./frontend/playwright-report . && tar tzf /out/project.tar.gz | grep -vc '/$'" > "%FM_DIR%\files.count" || goto fail
set "FM_FILES_COUNT="
for /f "usebackq delims=" %%n in ("%FM_DIR%\files.count") do if not defined FM_FILES_COUNT set "FM_FILES_COUNT=%%n"
del "%FM_DIR%\files.count"
set "FM_FILES_NOTE=%FM_FILES_COUNT% files, archive checked"
:filesdone
echo     %FM_FILES_NOTE%

echo 5/5 Writing the manifest ...
set "FM_GIT=unknown"
for /f %%c in ('git rev-parse --short HEAD 2^>nul') do set "FM_GIT=%%c"
set "FM_M=%FM_DIR%\manifest.txt"
> "%FM_M%" echo Future Mirror AI backup
>>"%FM_M%" echo Created:      %FM_TS:~0,4%-%FM_TS:~4,2%-%FM_TS:~6,2% %FM_TS:~9,2%:%FM_TS:~11,2%:%FM_TS:~13,2%
>>"%FM_M%" echo Code version: %FM_GIT%
>>"%FM_M%" echo Verification: %FM_VERDICT%
>>"%FM_M%" echo Project:      %FM_FILES_NOTE%
>>"%FM_M%" echo.
>>"%FM_M%" echo Files (SHA-256):
for %%f in (database.dump env.backup n8n.tar.gz project.tar.gz) do if exist "%FM_DIR%\%%f" call :hashline "%%f"
>>"%FM_M%" echo.
>>"%FM_M%" echo Rows per table in the verified copy:
for /f "usebackq tokens=1,2" %%a in ("%FM_DIR%\counts.txt") do >>"%FM_M%" echo   %%a  %%b
del "%FM_DIR%\counts.txt"
>>"%FM_M%" echo.
>>"%FM_M%" echo Restore with: ops\restore.bat %FM_NAME%   (macOS/Linux: ops/restore.sh %FM_NAME%)
>>"%FM_M%" echo Project folder lost? Unpack project.tar.gz into a new folder (tar -xzf project.tar.gz), copy this
>>"%FM_M%" echo backup folder into its backups folder, then run the restore command above from there.

if defined FM_COPY_TO call :copyoffsite
rem Retention: keep the newest FM_KEEP good backups (folders and older single-file dumps).
for /f "skip=%FM_KEEP% delims=" %%d in ('dir /b /o-n "backups\fm_*" 2^>nul') do call :removeold "%%d"

echo.
echo Backup complete and verified: %CD%\%FM_DIR%
set "FM_DIR="
goto done

:hashline
set "FM_HASH="
for /f "skip=1 delims=" %%h in ('certutil -hashfile "%FM_DIR%\%~1" SHA256') do if not defined FM_HASH set "FM_HASH=%%h"
if defined FM_HASH set "FM_HASH=%FM_HASH: =%"
for %%s in ("%FM_DIR%\%~1") do >>"%FM_M%" echo   %~1  %%~zs bytes  %FM_HASH%
exit /b 0

:copyoffsite
if not exist "%FM_COPY_TO%" mkdir "%FM_COPY_TO%" >nul 2>&1
xcopy /e /i /q /y "%FM_DIR%" "%FM_COPY_TO%\%FM_NAME%\" >nul 2>&1 || goto copyfailed
echo Second copy saved to: %FM_COPY_TO%\%FM_NAME%
exit /b 0
:copyfailed
echo WARNING: could not copy the backup to %FM_COPY_TO% - the backup in %FM_DIR% is fine
exit /b 0

:removeold
if exist "backups\%~1\" (rd /s /q "backups\%~1") else (del /q "backups\%~1")
echo Removed old backup: backups\%~1
exit /b 0

:fail
echo [FAILED] See the messages above.
rem A backup that did not finish (or failed verification) is renamed so it is never mistaken for a good one.
if defined FM_DIR if exist "%FM_DIR%" ren "%FM_DIR%" "failed_%FM_NAME%" && echo Incomplete backup moved to backups\failed_%FM_NAME%
set "FM_RC=1"
:done
if not defined FM_NO_PAUSE pause
exit /b %FM_RC%
