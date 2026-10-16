@echo off
rem Shared helpers for the Future Mirror AI scripts. Called as: call "%~dp0_common.bat" :label
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
rem Sets FM_PORT from FM_HTTP_PORT in .env (default 8080)
set "FM_PORT=8080"
if exist ".env" for /f "tokens=1,* delims==" %%a in ('findstr /b /c:"FM_HTTP_PORT=" ".env"') do if not "%%b"=="" set "FM_PORT=%%b"
exit /b 0

:waitdb
rem Waits until PostgreSQL accepts connections (up to ~2 minutes)
set /a FM_TRIES=0
:waitdb_loop
docker compose exec -T db sh -c "pg_isready -q -U $POSTGRES_USER -d $POSTGRES_DB" >nul 2>&1
if not errorlevel 1 exit /b 0
set /a FM_TRIES+=1
if %FM_TRIES% geq 40 (
  echo [ERROR] The database did not become ready. Check: docker compose logs db
  exit /b 1
)
timeout /t 3 /nobreak >nul
goto waitdb_loop

:waitapp
rem Waits until the web app answers on http://localhost:FM_PORT (up to ~4 minutes)
call :port
echo Waiting for the app on http://localhost:%FM_PORT% ...
set /a FM_TRIES=0
:waitapp_loop
curl -sf "http://localhost:%FM_PORT%/api/ready" >nul 2>&1
if not errorlevel 1 (
  echo The app is ready: http://localhost:%FM_PORT%
  exit /b 0
)
set /a FM_TRIES+=1
if %FM_TRIES% geq 80 (
  echo [ERROR] The app did not become ready. Check: docker compose logs backend
  exit /b 1
)
timeout /t 3 /nobreak >nul
goto waitapp_loop

:timestamp
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "FM_TS=%%i"
exit /b 0
