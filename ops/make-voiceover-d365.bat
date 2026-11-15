@echo off
rem Dynamics 365 F^&O + OData demo (Modern Standard Arabic) with a female voice and calm background music.
rem Put future-mirror-demo-d365.mp4 and future-mirror-demo-d365.srt in docs\video first.
rem   make-voiceover-d365.bat                      -^> ar-EG-SalmaNeural (the video is paced for her)
rem   make-voiceover-d365.bat ar-SA-ZariyahNeural  -^> another female voice
rem The music (docs\video\music-calm.mp3) sits 26 dB below the voice and dips further while she speaks.
rem Quieter: set FM_MUSIC_VOLUME=-30   Louder: set FM_MUSIC_VOLUME=-22   No music: set FM_MUSIC=none
rem Speed: natural by default (calm, about 20 minutes); set FM_VOICE_RATE=5 or 10 for faster.
if not defined FM_VOICE_RATE set "FM_VOICE_RATE=0"
if not defined FM_MUSIC_VOLUME set "FM_MUSIC_VOLUME=-26"
if not defined FM_MUSIC set "FM_MUSIC=docs\video\music-calm.mp3"
if /i "%FM_MUSIC%"=="none" set "FM_MUSIC="
set "FM_V=%~1"
if "%FM_V%"=="" set "FM_V=female"
call "%~dp0make-voiceover.bat" %FM_V% future-mirror-demo-d365
exit /b %errorlevel%
