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
echo [--] Python NON risulta installato, oppure non e' raggiungibile
echo      dal prompt dei comandi.
echo.
echo   Prima di rinunciare, controlla anche qui:
echo     - menu Start, cerca "Python"
echo     - cartella  %%LOCALAPPDATA%%\Programs\Python
echo     - cartella  C:\Program Files\Python311  (o Python312, Python313)
echo.
echo   Se davvero non c'e': l'installazione "solo per l'utente corrente"
echo   da python.org spesso NON richiede i diritti di amministratore.
echo   Se i criteri aziendali la bloccano, serve una richiesta all'IT.

:fine
echo.
pause
