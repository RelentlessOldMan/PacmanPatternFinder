@echo off
rem Start Pac-Man on a given level: pacman.bat 5   (or double-click and type the level)
rem Keep watch.lua next to this file and MAME in the mame-0.289 folder here (else D:\Mame is used).
rem The game races through the earlier levels, then slows to normal. 5 = coin, 1 = start, Esc = quit.
rem Each game is logged to the logs folder here as L<level>_<date>_<time>.log
set "MAME=%~dp0mame-0.289\mame.exe"
if not exist "%MAME%" set "MAME=D:\Mame\mame.exe"
set "PACMAN_LEVEL=%~1"
if "%PACMAN_LEVEL%"=="" set /p "PACMAN_LEVEL=Level: "
if "%PACMAN_LEVEL%"=="" set "PACMAN_LEVEL=1"
if not exist "%~dp0logs" mkdir "%~dp0logs"
for /f %%T in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "TS=%%T"
set "PACMAN_WATCH_LOG=%~dp0logs\L%PACMAN_LEVEL%_%TS%.log"
for %%F in ("%MAME%") do set "MAMEDIR=%%~dpF"
start "" /D "%MAMEDIR%" "%MAME%" pacman -window -notriplebuffer -lowlatency -skip_gameinfo -autoboot_script "%~dp0watch.lua"
