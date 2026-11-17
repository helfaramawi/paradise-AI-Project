@echo off
rem Load (or reset) the fictional DEMO dataset used for presentations. Never run this on a customer's data.
rem   seed-demo.bat          load the demo organisation if it does not exist
rem   seed-demo.bat reset    delete and recreate the demo organisation (other organisations are untouched)
setlocal
cd /d "%~dp0.."
set "HQ_ARG="
if /i "%~1"=="reset" set "HQ_ARG=--reset"
docker compose exec -T backend python -m app.demo.seed %HQ_ARG%
echo Demo accounts: ceo@haqq.demo, commercial@haqq.demo, contracts@haqq.demo, cfo@haqq.demo ... password HaqqDemo!2026
pause
