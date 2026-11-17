@echo off
rem Shared helpers for the HAQQ scripts. Called as: call "%~dp0_common.bat" :label
goto %~1

:checkdocker
docker info >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Docker is not running. Start Docker Desktop, wait until it says "running", then try again.
  exit /b 1
)
docker compose version >nul 2>&1
if errorlevel 1 (
  echo [ERROR] "docker compose" is not available. Update Docker Desktop.
  exit /b 1
)
exit /b 0

:port
rem Sets HQ_PORT from HAQQ_HTTP_PORT in .env (default 8090)
set "HQ_PORT=8090"
if exist ".env" for /f "tokens=1,* delims==" %%a in ('findstr /b /c:"HAQQ_HTTP_PORT=" ".env"') do if not "%%b"=="" set "HQ_PORT=%%b"
exit /b 0

:waitdb
set /a HQ_TRIES=0
:waitdb_loop
docker compose exec -T db sh -c "pg_isready -q -U $POSTGRES_USER -d $POSTGRES_DB" >nul 2>&1
if not errorlevel 1 exit /b 0
set /a HQ_TRIES+=1
if %HQ_TRIES% geq 40 (
  echo [ERROR] The database did not become ready. Check: docker compose logs db
  exit /b 1
)
timeout /t 3 /nobreak >nul
goto waitdb_loop

:waitapp
call :port
echo Waiting for HAQQ on http://localhost:%HQ_PORT% ...
set /a HQ_TRIES=0
:waitapp_loop
curl -sf "http://localhost:%HQ_PORT%/api/health/ready" >nul 2>&1
if not errorlevel 1 (
  echo HAQQ is ready: http://localhost:%HQ_PORT%
  exit /b 0
)
set /a HQ_TRIES+=1
if %HQ_TRIES% geq 100 (
  echo [ERROR] HAQQ did not become ready. Check: docker compose logs backend
  exit /b 1
)
timeout /t 3 /nobreak >nul
goto waitapp_loop

:timestamp
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "HQ_TS=%%i"
exit /b 0
