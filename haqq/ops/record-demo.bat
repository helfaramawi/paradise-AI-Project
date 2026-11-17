@echo off
rem Records the Arabic HAQQ demo video (about 10 minutes, real time) from the running app with fresh DEMO data.
rem Needs: HAQQ running (ops\start.bat), Node.js 22 (winget install -e --id OpenJS.NodeJS.LTS) and FFmpeg.
rem Output: haqq\docs\video\haqq-demo-ar.mp4 + haqq-demo-ar.srt  -> then run ops\make-voiceover.bat
setlocal
set "HQ_RC=0"
cd /d "%~dp0.."
call "%~dp0_common.bat" :port
where node >nul 2>&1 || (echo [ERROR] Node.js is not installed: winget install -e --id OpenJS.NodeJS.LTS & goto fail)
where ffmpeg >nul 2>&1 || (echo [ERROR] FFmpeg is not installed: winget install -e --id Gyan.FFmpeg & goto fail)
echo Resetting the DEMO data so dates and amounts match the script ...
docker compose exec -T backend python -m app.demo.seed --reset >nul || goto fail
cd frontend
if not exist node_modules (call npm ci --no-audit --no-fund || goto fail)
call npx playwright install chromium || goto fail
set "BASE_URL=http://localhost:%HQ_PORT%"
set "OUT_DIR=..\docs\video"
echo Recording ... do not use the computer's browser windows meanwhile.
node e2e\video\record-demo-ar.mjs || goto fail
echo Done: docs\video\haqq-demo-ar.mp4 - now run ops\make-voiceover.bat
goto done
:fail
echo [FAILED] See the messages above.
set "HQ_RC=1"
:done
pause
exit /b %HQ_RC%
