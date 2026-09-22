@echo off
rem Avvio di SGS Live su Windows: doppio clic su questo file.
setlocal
cd /d "%~dp0"
title SGS Live

set "PYCMD="
py -3 --version >nul 2>&1
if not errorlevel 1 set "PYCMD=py -3"
if defined PYCMD goto trovato
python --version >nul 2>&1
if not errorlevel 1 set "PYCMD=python"
if defined PYCMD goto trovato
goto senza_python

:trovato
if exist ".venv\Scripts\python.exe" goto avvio
echo.
echo Prima installazione: preparo il programma, puo' richiedere qualche minuto.
echo.
%PYCMD% -m venv .venv
if errorlevel 1 goto errore
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto errore

:avvio
".venv\Scripts\python.exe" sgs.py %*
echo.
echo SGS Live e' stato chiuso.
pause
exit /b 0

:senza_python
echo.
echo Python non risulta installato su questo computer.
echo Installalo da https://www.python.org/downloads/windows/
echo IMPORTANTE: nella prima schermata spunta "Add python.exe to PATH".
echo.
pause
exit /b 1

:errore
echo.
echo Installazione non riuscita. Se il PC e' dietro il proxy aziendale,
echo segnala questo messaggio all'assistenza informatica.
echo.
pause
exit /b 1
