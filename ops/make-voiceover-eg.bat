@echo off
rem Egyptian-dialect demo (collections question) with the Egyptian female voice (ar-EG-SalmaNeural).
rem Put future-mirror-demo-eg.mp4 and future-mirror-demo-eg.srt in docs\video first.
call "%~dp0make-voiceover.bat" female future-mirror-demo-eg
exit /b %errorlevel%
