@echo off
rem Start the local Dynamics 365 Finance and Operations simulator (Arabic test data) and connect Future Mirror to it.
rem   ops\d365-sim.bat         start, configure the Dynamics 365 Finance and Operations connection and test it
rem   ops\d365-sim.bat stop    stop the simulator only
rem See docs\D365_FO_TESTING.md.
setlocal
set "FM_RC=0"
cd /d "%~dp0.."
call "%~dp0_common.bat" :checkdocker || goto fail
if /i "%~1"=="stop" (
  docker compose --profile d365sim stop d365fo-sim || goto fail
  echo Simulator stopped. Future Mirror keeps running.
  goto done
)
if not exist ".env" type nul > ".env"
call :setenv FM_D365_FO_CLIENT_SECRET fm-sim-secret-2026 || goto fail
call :setenv FM_D365_CA_BUNDLE /certs/d365sim/ca.pem || goto fail
echo Starting Future Mirror AI with the Dynamics 365 F^&O simulator ...
docker compose --profile d365sim up -d --build || goto fail
call "%~dp0_common.bat" :waitapp || goto fail
set "FM_SIM_PORT=8443"
for /f "tokens=1,* delims==" %%a in ('findstr /b /c:"FM_D365_SIM_PORT=" ".env"') do if not "%%b"=="" set "FM_SIM_PORT=%%b"
echo Connecting Future Mirror to the simulator ...
docker compose --profile d365sim run --rm --no-deps d365fo-sim python -m d365fo_sim.configure_fm || goto fail
echo.
echo Done. Test data in the browser: https://localhost:%FM_SIM_PORT% (accept the certificate warning).
echo In Future Mirror open Data Connections, Dynamics 365 Finance ^& Operations, and press Sync.
start "" "https://localhost:%FM_SIM_PORT%"
start "" "http://localhost:%FM_PORT%"
goto done
:setenv
rem Sets %1=%2 in .env unless %1 already has a value there (UTF-8, no BOM).
set "FM_HAS="
for /f "tokens=1,* delims==" %%a in ('findstr /b /c:"%~1=" ".env"') do if not "%%b"=="" set "FM_HAS=1"
if defined FM_HAS exit /b 0
powershell -NoProfile -Command "$p=(Resolve-Path '.env').Path; $l=@([IO.File]::ReadAllLines($p) | Where-Object { $_ -notmatch '^%~1=' }); $l += '%~1=%~2'; [IO.File]::WriteAllLines($p, [string[]]$l)" || exit /b 1
echo Set %~1 in .env
exit /b 0
:fail
echo [FAILED] See the messages above.
set "FM_RC=1"
:done
if not defined FM_NO_PAUSE pause
exit /b %FM_RC%
