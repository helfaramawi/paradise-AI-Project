@echo off
rem Egyptian-dialect demo (collections question) with the Egyptian female voice (ar-EG-SalmaNeural).
rem Put future-mirror-demo-eg.mp4 and future-mirror-demo-eg.srt in docs\video first.
rem Salma reads the fully diacritised captions slowly; 10% faster keeps the video near 15 minutes and still
rem sounds natural. Change it with: set FM_VOICE_RATE=0 (natural) or 15 (faster) before running.
if not defined FM_VOICE_RATE set "FM_VOICE_RATE=10"
call "%~dp0make-voiceover.bat" female future-mirror-demo-eg
exit /b %errorlevel%
