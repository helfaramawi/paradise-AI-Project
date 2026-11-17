@echo off
rem Full, VERIFIED backup of HAQQ into haqq\backups\haqq_YYYYMMDD_HHMMSS\ :
rem   database.dump      all application data (PostgreSQL custom-format dump)
rem   documents.tar.gz   every uploaded document and generated claim file (object storage)
rem   env.backup         the .env file (passwords, API keys) - keep backups PRIVATE
rem   manifest.txt       time, code version, both verification results, row counts, SHA-256 checksums
rem Verification: the dump is test-restored into a scratch database and compared table by table with the
rem live data, and every stored file in documents.tar.gz is checked against the SHA-256 recorded in the database.
rem Options (environment or .env): HAQQ_BACKUP_KEEP=30 (newest backups kept), HAQQ_BACKUP_COPY_TO=D:\Backups\HAQQ
rem (second copy, e.g. an external or network drive).   Usage: backup.bat [/nopause]
setlocal
set "HQ_RC=0"
set "HQ_DIR="
if /i "%~1"=="/nopause" set "HQ_NO_PAUSE=1"
cd /d "%~dp0.."
call "%~dp0_common.bat" :checkdocker || goto fail

set "HQ_KEEP=%HAQQ_BACKUP_KEEP%"
set "HQ_COPY_TO=%HAQQ_BACKUP_COPY_TO%"
if exist ".env" if not defined HQ_KEEP for /f "tokens=1,* delims==" %%a in ('findstr /b /c:"HAQQ_BACKUP_KEEP=" ".env"') do set "HQ_KEEP=%%b"
if exist ".env" if not defined HQ_COPY_TO for /f "tokens=1,* delims==" %%a in ('findstr /b /c:"HAQQ_BACKUP_COPY_TO=" ".env"') do set "HQ_COPY_TO=%%b"
if not defined HQ_KEEP set "HQ_KEEP=30"
set /a HQ_KEEP=HQ_KEEP+0 2>nul
if %HQ_KEEP% lss 1 set "HQ_KEEP=30"

call "%~dp0_common.bat" :timestamp
set "HQ_NAME=haqq_%HQ_TS%"
set "HQ_DIR=backups\%HQ_NAME%"
mkdir "%HQ_DIR%" || goto fail
docker compose up -d db || goto fail
call "%~dp0_common.bat" :waitdb || goto fail
docker compose cp "ops\db\haqq_db.sh" db:/tmp/haqq_db.sh >nul 2>&1 || goto fail

echo 1/5 Backing up the database ...
docker compose exec -T db sh /tmp/haqq_db.sh backup /tmp/haqq_backup.dump || goto fail
docker compose cp db:/tmp/haqq_backup.dump "%HQ_DIR%\database.dump" >nul 2>&1 || goto fail

echo 2/5 Verifying the database backup by restoring it into a scratch database ...
docker compose exec -T db sh /tmp/haqq_db.sh verify /tmp/haqq_backup.dump > "%HQ_DIR%\verify.txt"
if errorlevel 1 (
  type "%HQ_DIR%\verify.txt"
  echo [ERROR] Database backup verification failed - this backup is NOT usable.
  goto fail
)
set "HQ_DB_VERDICT="
for /f "usebackq delims=" %%v in ("%HQ_DIR%\verify.txt") do if not defined HQ_DB_VERDICT set "HQ_DB_VERDICT=%%v"
del "%HQ_DIR%\verify.txt"
echo     %HQ_DB_VERDICT%
docker compose exec -T db cat /tmp/haqq_restored_counts.txt > "%HQ_DIR%\counts.txt" || goto fail
docker compose exec -T db rm -f /tmp/haqq_backup.dump /tmp/haqq_db.sh /tmp/haqq_live_counts.txt /tmp/haqq_restored_counts.txt /tmp/haqq_verify.log >nul 2>&1

echo 3/5 Backing up documents and generated claim files ...
docker compose run --rm --no-deps -v "%CD%\%HQ_DIR%:/out" --entrypoint sh backend -c "tar czf /out/documents.tar.gz -C /data storage" || goto fail

echo 4/5 Verifying every stored file against its SHA-256 in the database ...
docker compose run --rm --no-deps -v "%CD%\%HQ_DIR%:/out:ro" backend python -m app.ops_tools verify-archive /out/documents.tar.gz > "%HQ_DIR%\docverify.txt"
if errorlevel 1 (
  type "%HQ_DIR%\docverify.txt"
  echo [ERROR] Document archive verification failed - this backup is NOT usable.
  goto fail
)
set "HQ_DOC_VERDICT="
for /f "usebackq delims=" %%v in ("%HQ_DIR%\docverify.txt") do if not defined HQ_DOC_VERDICT set "HQ_DOC_VERDICT=%%v"
del "%HQ_DIR%\docverify.txt"
echo     %HQ_DOC_VERDICT%

echo 5/5 Saving configuration and writing the manifest ...
if exist ".env" (
  copy /y ".env" "%HQ_DIR%\env.backup" >nul || goto fail
) else (
  echo     no .env file - defaults in use
)
set "HQ_GIT=unknown"
for /f %%c in ('git rev-parse --short HEAD 2^>nul') do set "HQ_GIT=%%c"
set "HQ_M=%HQ_DIR%\manifest.txt"
> "%HQ_M%" echo HAQQ backup
>>"%HQ_M%" echo Created:      %HQ_TS:~0,4%-%HQ_TS:~4,2%-%HQ_TS:~6,2% %HQ_TS:~9,2%:%HQ_TS:~11,2%:%HQ_TS:~13,2%
>>"%HQ_M%" echo Code version: %HQ_GIT%
>>"%HQ_M%" echo Database:     %HQ_DB_VERDICT%
>>"%HQ_M%" echo Documents:    %HQ_DOC_VERDICT%
>>"%HQ_M%" echo.
>>"%HQ_M%" echo Files (SHA-256):
for %%f in (database.dump documents.tar.gz env.backup) do if exist "%HQ_DIR%\%%f" call :hashline "%%f"
>>"%HQ_M%" echo.
>>"%HQ_M%" echo Rows per table in the verified copy:
for /f "usebackq tokens=1,2" %%a in ("%HQ_DIR%\counts.txt") do >>"%HQ_M%" echo   %%a  %%b
del "%HQ_DIR%\counts.txt"
>>"%HQ_M%" echo.
>>"%HQ_M%" echo Restore with: ops\restore.bat %HQ_NAME%   (macOS/Linux: ops/restore.sh %HQ_NAME%)
>>"%HQ_M%" echo New machine: clone the repository, install Docker Desktop, copy this folder into haqq\backups, run the command above.

if defined HQ_COPY_TO call :copyoffsite
rem Retention: keep the newest HQ_KEEP good backups.
for /f "skip=%HQ_KEEP% delims=" %%d in ('dir /b /ad /o-n "backups\haqq_*" 2^>nul') do call :removeold "%%d"

echo.
echo Backup complete and verified: %CD%\%HQ_DIR%
set "HQ_DIR="
goto done

:hashline
set "HQ_HASH="
for /f "skip=1 delims=" %%h in ('certutil -hashfile "%HQ_DIR%\%~1" SHA256') do if not defined HQ_HASH set "HQ_HASH=%%h"
if defined HQ_HASH set "HQ_HASH=%HQ_HASH: =%"
for %%s in ("%HQ_DIR%\%~1") do >>"%HQ_M%" echo   %~1  %%~zs bytes  %HQ_HASH%
exit /b 0

:copyoffsite
if not exist "%HQ_COPY_TO%" mkdir "%HQ_COPY_TO%" >nul 2>&1
xcopy /e /i /q /y "%HQ_DIR%" "%HQ_COPY_TO%\%HQ_NAME%\" >nul 2>&1 || goto copyfailed
echo Second copy saved to: %HQ_COPY_TO%\%HQ_NAME%
exit /b 0
:copyfailed
echo WARNING: could not copy the backup to %HQ_COPY_TO% - the backup in %HQ_DIR% is fine
exit /b 0

:removeold
rd /s /q "backups\%~1"
echo Removed old backup: backups\%~1
exit /b 0

:fail
echo [FAILED] See the messages above.
rem An unfinished or unverified backup is renamed so it is never mistaken for a good one.
if defined HQ_DIR if exist "%HQ_DIR%" ren "%HQ_DIR%" "failed_%HQ_NAME%" && echo Incomplete backup moved to backups\failed_%HQ_NAME%
set "HQ_RC=1"
:done
if not defined HQ_NO_PAUSE pause
exit /b %HQ_RC%
