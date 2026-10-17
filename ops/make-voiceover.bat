@echo off
rem Adds a natural Arabic voice-over to the demo video (Microsoft neural voices, free).
rem   make-voiceover.bat            -> Egyptian male voice  (ar-EG-ShakirNeural)
rem   make-voiceover.bat female     -> Egyptian female voice (ar-EG-SalmaNeural)
rem   make-voiceover.bat ar-SA-HamedNeural   -> any Edge voice name
rem Put future-mirror-demo-ar.mp4 and future-mirror-demo-ar.srt in docs\video first.
rem Optional background music: save it as docs\video\music.mp3 (or .m4a / .wav); it is kept low and ducked under the voice.
setlocal
set "FM_RC=0"
cd /d "%~dp0.."
set "VOICE=ar-EG-ShakirNeural"
if /i "%~1"=="female" set "VOICE=ar-EG-SalmaNeural"
if /i "%~1"=="male" set "VOICE=ar-EG-ShakirNeural"
echo %~1 | findstr /b /c:"ar-" >nul && set "VOICE=%~1"

set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY where python >nul 2>&1 && set "PY=python"
if not defined PY (
  echo [ERROR] Python is not installed.
  echo Install it with:  winget install -e --id Python.Python.3.12
  echo or from https://www.python.org/downloads/  ^(tick "Add python.exe to PATH"^), then run this again.
  goto fail
)
where ffmpeg >nul 2>&1
if errorlevel 1 (
  echo [ERROR] FFmpeg is not installed.
  echo Install it with:  winget install -e --id Gyan.FFmpeg
  echo then CLOSE this window, open a new one, and run this again.
  goto fail
)
if not exist "docs\video\future-mirror-demo-ar.mp4" (
  echo [ERROR] docs\video\future-mirror-demo-ar.mp4 not found.
  echo Copy the demo video and its .srt file into the docs\video folder, then run this again.
  goto fail
)
if not exist "docs\video\future-mirror-demo-ar.srt" (
  echo [ERROR] docs\video\future-mirror-demo-ar.srt not found.
  goto fail
)
echo Installing / updating the voice engine ^(edge-tts^) ...
%PY% -m pip install --quiet --upgrade edge-tts || goto fail
echo Generating the Arabic voice-over with %VOICE% ^(about 3-5 minutes^) ...
set "MUSIC_ARG="
for %%m in (docs\video\music.mp3 docs\video\music.m4a docs\video\music.wav) do if exist "%%m" set "MUSIC_ARG=--music %%m"
if defined MUSIC_ARG (echo Background music found: %MUSIC_ARG:--music =%) else (echo No background music ^(to add some, save it as docs\video\music.mp3^))
%PY% scripts\voiceover\make_voiceover.py --video docs\video\future-mirror-demo-ar.mp4 --srt docs\video\future-mirror-demo-ar.srt --voice %VOICE% %MUSIC_ARG% || goto fail
echo.
echo Done: docs\video\future-mirror-demo-ar-voice.mp4
explorer /select,"%CD%\docs\video\future-mirror-demo-ar-voice.mp4"
goto done
:fail
echo [FAILED] See the messages above.
set "FM_RC=1"
:done
pause
exit /b %FM_RC%
