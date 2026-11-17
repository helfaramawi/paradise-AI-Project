@echo off
rem Schedule an automatic, verified HAQQ backup every day with Windows Task Scheduler.
rem   schedule-backup.bat          -> daily at 23:30
rem   schedule-backup.bat 02:00    -> daily at 02:00
rem   schedule-backup.bat remove   -> remove the scheduled backup
rem The computer must be on and Docker Desktop running at that time. Results: haqq\backups\last-scheduled.log
setlocal
set "HQ_TIME=%~1"
if /i "%HQ_TIME%"=="remove" (
  schtasks /delete /tn "HAQQ daily backup" /f && echo Scheduled backup removed.
  goto end
)
if "%HQ_TIME%"=="" set "HQ_TIME=23:30"
if not exist "%~dp0..\backups" mkdir "%~dp0..\backups"
schtasks /create /tn "HAQQ daily backup" /sc daily /st %HQ_TIME% /f /tr "cmd /c \"\"%~dp0backup.bat\" /nopause > \"%~dp0..\backups\last-scheduled.log\" 2>&1\"" || goto end
echo Daily backup scheduled at %HQ_TIME%. Check results in haqq\backups\last-scheduled.log
:end
pause
