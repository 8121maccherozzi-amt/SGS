@echo off
rem Verifica se questo PC ha gia' tutto il necessario per SGS Live.
rem Non installa nulla e non modifica nulla.
setlocal
title Verifica requisiti - SGS Live
echo.
echo ==========================================================
echo   SGS Live - verifica dei requisiti (nessuna modifica)
echo ==========================================================
echo.

set "TROVATO="
py --version >nul 2>&1
if not errorlevel 1 set "TROVATO=py"
if defined TROVATO goto controlla
python --version >nul 2>&1
if not errorlevel 1 set "TROVATO=python"
if defined TROVATO goto controlla
python3 --version >nul 2>&1
if not errorlevel 1 set "TROVATO=python3"
if defined TROVATO goto controlla
goto assente

:controlla
echo [OK] Python risulta gia' installato su questo computer.
echo      Comando: %TROVATO%
for /f "delims=" %%V in ('%TROVATO% --version 2^>^&1') do echo      Versione: %%V
for /f "delims=" %%P in ('%TROVATO% -c "import sys;print(sys.executable)" 2^>nul') do echo      Percorso: %%P
echo.

%TROVATO% -c "import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>&1
if errorlevel 1 goto vecchia
echo [OK] La versione e' sufficiente (serve 3.10 o superiore).

%TROVATO% -m venv --help >nul 2>&1
if errorlevel 1 goto senzavenv
echo [OK] Il componente per creare l'ambiente di lavoro e' presente.

%TROVATO% -m pip --version >nul 2>&1
if errorlevel 1 goto senzapip
echo [OK] Il gestore dei componenti aggiuntivi (pip) e' presente.
echo.
echo ----------------------------------------------------------
echo   ESITO: questo PC e' pronto.
echo   Puoi fare doppio clic su "avvia.bat".
echo ----------------------------------------------------------
goto fine

:vecchia
echo [!!] La versione installata e' troppo vecchia: serve Python 3.10 o superiore.
echo      Va segnalato all'assistenza informatica.
goto fine

:senzavenv
echo [!!] Manca il componente "venv" (capita con alcune installazioni ridotte).
echo      Va segnalato all'assistenza informatica.
goto fine

:senzapip
echo [!!] Manca "pip", il gestore dei componenti aggiuntivi.
echo      Va segnalato all'assistenza informatica.
goto fine

:assente
echo [--] Python non risponde dal prompt dei comandi.
echo      Cerco se e' comunque presente sul computer, installato da
echo      qualche altro programma (Anaconda, software tecnico, ecc.)...
echo.

set "NASCOSTO="
for %%D in (
  "%LOCALAPPDATA%\Programs\Python"
  "%LOCALAPPDATA%\Microsoft\WindowsApps"
  "%LOCALAPPDATA%\Continuum"
  "%USERPROFILE%\Anaconda3"
  "%USERPROFILE%\Miniconda3"
  "%USERPROFILE%\AppData\Local\anaconda3"
  "C:\Python313" "C:\Python312" "C:\Python311" "C:\Python310"
  "C:\Program Files\Python313" "C:\Program Files\Python312"
  "C:\Program Files\Python311" "C:\Program Files\Python310"
  "C:\ProgramData\Anaconda3" "C:\Anaconda3"
) do call :cerca %%D

if defined NASCOSTO goto trovato_nascosto

echo   Nessuna installazione trovata nelle posizioni consuete.
echo.
echo   Cosa puoi provare, in ordine:
echo     1) Scrivi solo  python  nel prompt e premi Invio: se si apre il
echo        Microsoft Store, prova a installarlo da li' (non serve
echo        l'amministratore; spesso pero' e' bloccato in azienda).
echo     2) Installa da https://www.python.org/downloads/windows/
echo        scegliendo "Install for me only" / "solo per me".
echo     3) Se entrambe sono bloccate, serve una richiesta all'assistenza
echo        informatica.
goto fine

:trovato_nascosto
echo.
echo [OK] Trovata un'installazione di Python qui:
echo      %NASCOSTO%
echo.
echo   Non e' raggiungibile dal prompt, ma il programma puo' usarla lo stesso.
echo   Segnala questo percorso e ti indico come avviare SGS Live con questa.
goto fine

:cerca
if defined NASCOSTO goto :eof
if exist "%~1\python.exe" set "NASCOSTO=%~1\python.exe"
if defined NASCOSTO goto :eof
for /d %%S in ("%~1\Python3*") do if exist "%%~S\python.exe" set "NASCOSTO=%%~S\python.exe"
goto :eof

:fine
echo.
pause
