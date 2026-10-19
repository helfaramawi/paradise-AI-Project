@echo off
rem Port Said Free Zone demo (collections question, Modern Standard Arabic) with a female voice.
rem Put future-mirror-demo-collections.mp4 and future-mirror-demo-collections.srt in docs\video first.
rem   make-voiceover-collections.bat                      -> ar-EG-SalmaNeural (the video is paced for her)
rem   make-voiceover-collections.bat ar-SA-ZariyahNeural  -> another female voice
rem Salma reads the fully diacritised captions slowly; 10% faster keeps the video near 15 minutes and still
rem sounds natural. Change it with: set FM_VOICE_RATE=0 (natural) or 15 (faster) before running.
if not defined FM_VOICE_RATE set "FM_VOICE_RATE=10"
set "FM_V=%~1"
if "%FM_V%"=="" set "FM_V=female"
call "%~dp0make-voiceover.bat" %FM_V% future-mirror-demo-collections
exit /b %errorlevel%
