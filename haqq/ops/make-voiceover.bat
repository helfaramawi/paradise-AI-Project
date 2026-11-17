@echo off
rem Adds a natural Egyptian Arabic voice-over (Microsoft neural voices, free, needs internet) to the HAQQ demo video.
rem   make-voiceover.bat            -> male voice   (ar-EG-ShakirNeural)
rem   make-voiceover.bat female     -> female voice (ar-EG-SalmaNeural)
rem   make-voiceover.bat ar-SA-HamedNeural   -> any Edge voice name
rem Needs haqq\docs\video\haqq-demo-ar.mp4 and haqq-demo-ar.srt (from record-demo.bat).
rem Background music: the calm track in the repository (docs\video\music-calm.mp3) is mixed in low under the voice.
rem   set HQ_MUSIC=none to leave music out; set HQ_MUSIC=C:\path\music.mp3 for another track;
rem   set HQ_MUSIC_VOLUME=-20 (dB below the voice, default -24); set HQ_VOICE_RATE=5 (speak 5% faster).
rem Output: haqq\docs\video\haqq-demo-ar-voice.mp4
setlocal
set "HQ_RC=0"
cd /d "%~dp0.."
set "VOICE=ar-EG-ShakirNeural"
if /i "%~1"=="female" set "VOICE=ar-EG-SalmaNeural"
echo %~1 | findstr /b /c:"ar-" >nul && set "VOICE=%~1"
set "VIDEO=haqq-demo-ar"
set "RATE_ARG="
if defined HQ_VOICE_RATE set "RATE_ARG=--rate %HQ_VOICE_RATE%"

set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY where python >nul 2>&1 && set "PY=python"
if not defined PY (
  echo [ERROR] Python is not installed. Install it with:  winget install -e --id Python.Python.3.12
  goto fail
)
where ffmpeg >nul 2>&1
if errorlevel 1 (
  echo [ERROR] FFmpeg is not installed. Install it with:  winget install -e --id Gyan.FFmpeg
  echo then CLOSE this window, open a new one, and run this again.
  goto fail
)
if not exist "docs\video\%VIDEO%.mp4" (
  echo [ERROR] docs\video\%VIDEO%.mp4 not found. Record it first with ops\record-demo.bat
  goto fail
)
if not exist "docs\video\%VIDEO%.srt" (
  echo [ERROR] docs\video\%VIDEO%.srt not found. Record it first with ops\record-demo.bat
  goto fail
)
set "MUSIC_ARG="
if exist "..\docs\video\music-calm.mp3" set "MUSIC_ARG=--music ..\docs\video\music-calm.mp3"
if defined HQ_MUSIC if /i "%HQ_MUSIC%"=="none" set "MUSIC_ARG="
if defined HQ_MUSIC if exist "%HQ_MUSIC%" set "MUSIC_ARG=--music %HQ_MUSIC%"
if not defined HQ_MUSIC_VOLUME set "HQ_MUSIC_VOLUME=-24"
if defined MUSIC_ARG set "MUSIC_ARG=%MUSIC_ARG% --music-volume %HQ_MUSIC_VOLUME%"
echo Installing / updating the voice engine (edge-tts) ...
%PY% -m pip install --quiet --upgrade edge-tts || goto fail
echo Generating the Arabic voice-over with %VOICE% (about 3-5 minutes) ...
%PY% ..\scripts\voiceover\make_voiceover.py --video docs\video\%VIDEO%.mp4 --srt docs\video\%VIDEO%.srt --voice %VOICE% %RATE_ARG% %MUSIC_ARG% || goto fail
echo.
echo Done: docs\video\%VIDEO%-voice.mp4
explorer /select,"%CD%\docs\video\%VIDEO%-voice.mp4"
goto done
:fail
echo [FAILED] See the messages above.
set "HQ_RC=1"
:done
pause
exit /b %HQ_RC%
