@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

rem ======================================================================
rem  Adventurer-Kings - GM Interface Launcher
rem  Scarica (o aggiorna) il progetto, prepara Python e apre l'interfaccia.
rem  Per fermare gli aggiornamenti automatici (versione "congelata" per il
rem  playtest) crea un file vuoto BLOCCA_AGGIORNAMENTI.txt accanto a questo.
rem ======================================================================

set "REPO_URL=https://github.com/Fusky1975/programma-ak.git"
set "DEST=%USERPROFILE%\Documents\programma-ak"
set "PORT=5055"
set "HERE=%~dp0"

rem Modalita' "portatile": se accanto a questo file c'e' la cartella ak_engine
rem (zip di playtest) il programma si usa da li' e non serve ne' Git ne' GitHub.
set "PORTABLE="
if exist "%HERE%ak_engine\pyproject.toml" (
    set "PORTABLE=1"
    set "DEST=%HERE:~0,-1%"
)
if defined PORTABLE (
    set "VENV=%USERPROFILE%\ak_games\.venv"
) else (
    set "VENV=%DEST%\.venv"
)
set "MARK=%VENV%\ak_installed_commit.txt"

echo ============================================
echo   Adventurer-Kings - GM Interface Launcher
echo ============================================
echo.

rem --- Git (non serve in modalita' portatile) ---------------------------
if defined PORTABLE goto :SkipGit
where git >nul 2>nul
if errorlevel 1 (
    echo Git non trovato. Provo a installarlo con winget...
    where winget >nul 2>nul
    if not errorlevel 1 winget install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements
    call :RefreshPath
    where git >nul 2>nul
    if errorlevel 1 (
        echo.
        echo ERRORE: non sono riuscito a installare Git automaticamente.
        echo Installalo da https://git-scm.com/download/win
        echo poi fai doppio clic di nuovo su questo file.
        pause
        exit /b 1
    )
    echo Git installato correttamente.
)
:SkipGit

rem --- Python 3.11 o piu' recente ----------------------------------------
call :FindPython
if not defined PY (
    echo Python 3.11 o piu' recente non trovato. Provo a installarlo con winget...
    where winget >nul 2>nul
    if not errorlevel 1 winget install --id Python.Python.3.12 -e --source winget --accept-package-agreements --accept-source-agreements
    call :RefreshPath
    call :FindPython
    if not defined PY (
        echo.
        echo ERRORE: non sono riuscito a installare Python automaticamente.
        echo Installalo da https://www.python.org/downloads/
        echo ^(spunta "Add python.exe to PATH" durante l'installazione^)
        echo poi fai doppio clic di nuovo su questo file.
        pause
        exit /b 1
    )
    echo Python installato correttamente.
)
echo Python trovato: %PY%
echo.

rem --- Scarica o aggiorna il progetto ------------------------------------
if defined PORTABLE goto :SkipFetch
if exist "%DEST%\.git" (
    if exist "%HERE%BLOCCA_AGGIORNAMENTI.txt" (
        echo Aggiornamenti bloccati ^(BLOCCA_AGGIORNAMENTI.txt^): uso la copia presente.
    ) else (
        echo Cerco aggiornamenti del progetto...
        pushd "%DEST%"
        git checkout main >nul 2>nul
        git fetch origin
        if errorlevel 1 (
            echo.
            echo ATTENZIONE: non riesco a contattare GitHub ^(controlla la connessione^).
            echo Continuo con la copia gia' presente sul disco.
        ) else (
            rem Allinea la copia locale a quella online: un semplice "git pull"
            rem puo' fallire se la cartella ha anche solo una modifica locale.
            git reset --hard origin/main
            if errorlevel 1 (
                echo.
                echo ATTENZIONE: aggiornamento non riuscito. Continuo con la copia presente.
            )
        )
        popd
    )
) else (
    echo Scarico il progetto in:
    echo   %DEST%
    echo.
    echo Il progetto e' privato: la prima volta GitHub puo' aprire il browser per
    echo farti accedere con il tuo account ^(devi essere stato invitato^).
    echo.
    git clone "%REPO_URL%" "%DEST%"
    if errorlevel 1 (
        echo.
        echo ERRORE: scaricamento non riuscito. Controlla di avere accettato l'invito
        echo al repository, di aver fatto il login a GitHub e di essere online.
        pause
        exit /b 1
    )
)

:SkipFetch

set "HEAD="
echo.
echo Versione in uso:
if defined PORTABLE (
    if exist "%DEST%\VERSION.txt" (
        type "%DEST%\VERSION.txt"
        set /p HEAD=<"%DEST%\VERSION.txt"
    )
) else (
    for /f %%H in ('git -C "%DEST%" rev-parse HEAD 2^>nul') do set "HEAD=%%H"
    git -C "%DEST%" log -1 --format="  %%h  %%cd  %%s" --date=short
)
echo.

if not exist "%DEST%\launcher\run_server.py" (
    echo ERRORE: la copia scaricata non contiene launcher\run_server.py.
    echo Cancella la cartella "%DEST%" e rilancia questo file.
    pause
    exit /b 1
)

rem --- Ambiente Python dedicato ------------------------------------------
if not exist "%VENV%\Scripts\python.exe" (
    echo Creo l'ambiente Python dedicato...
    %PY% -m venv "%VENV%"
    if errorlevel 1 (
        echo.
        echo ERRORE durante la creazione dell'ambiente Python.
        pause
        exit /b 1
    )
    if exist "%MARK%" del "%MARK%"
)

rem Installa i componenti solo la prima volta o quando la versione cambia.
set "INSTALLED="
if exist "%MARK%" set /p INSTALLED=<"%MARK%"
if /i not "!INSTALLED!"=="!HEAD!" (
    echo Installo/aggiorno i componenti necessari ^(puo' richiedere qualche minuto
    echo la prima volta^)...
    "%VENV%\Scripts\python.exe" -m pip install --upgrade pip --quiet
    if defined PORTABLE (
        rem Installazione normale, senza -e: cosi la cartella si puo spostare.
        "%VENV%\Scripts\python.exe" -m pip install --upgrade --force-reinstall "%DEST%\ak_engine[webapp]" --quiet
    ) else (
        "%VENV%\Scripts\python.exe" -m pip install -e "%DEST%\ak_engine[webapp]" --quiet
    )
    if errorlevel 1 (
        echo.
        echo ERRORE durante l'installazione dei componenti Python.
        pause
        exit /b 1
    )
    >"%MARK%" echo !HEAD!
)

rem --- Porta libera ------------------------------------------------------
rem Se un'istanza precedente di questo server e' rimasta aperta la chiude;
rem se la porta e' occupata da un altro programma prova la successiva.
set /a TRY=0
:PortLoop
set /a P=PORT+TRY
set "PID="
for /f "tokens=5" %%X in ('netstat -ano ^| findstr /R /C:":%P% .*LISTENING"') do set "PID=%%X"
if not defined PID goto :PortOk
set "OURS="
for /f "usebackq delims=" %%X in (`powershell -NoProfile -Command "(Get-CimInstance Win32_Process -Filter 'ProcessId=%PID%').CommandLine" 2^>nul ^| findstr /C:"run_server.py"`) do set "OURS=1"
if defined OURS (
    echo Chiudo la precedente istanza del server sulla porta %P%...
    taskkill /F /PID %PID% >nul 2>nul
    timeout /t 1 /nobreak >nul
    goto :PortOk
)
set /a TRY+=1
if %TRY% GEQ 10 (
    echo.
    echo ERRORE: le porte %PORT%-%P% sono tutte occupate da altri programmi.
    pause
    exit /b 1
)
goto :PortLoop
:PortOk

rem --- Avvio -------------------------------------------------------------
echo Avvio l'interfaccia GM sulla porta %P%...
start "GM Interface - Adventurer-Kings" "%VENV%\Scripts\python.exe" "%DEST%\launcher\run_server.py" %P%

rem Aspetta (fino a 20 secondi) che il server risponda, poi apre il browser.
powershell -NoProfile -Command "for($i=0;$i -lt 40;$i++){ try { Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:%P%/' -TimeoutSec 2 | Out-Null; exit 0 } catch { Start-Sleep -Milliseconds 500 } }; exit 1"
if errorlevel 1 (
    echo.
    echo ATTENZIONE: il server non risponde. Guarda la finestra "GM Interface"
    echo e il file %USERPROFILE%\ak_games\logs\server.log
    pause
    exit /b 1
)
start "" "http://127.0.0.1:%P%/"

echo.
echo ============================================
echo  L'interfaccia GM e' in esecuzione nella
echo  finestra "GM Interface - Adventurer-Kings".
echo.
echo  Per CHIUDERE il server chiudi quella
echo  finestra ^(questa puoi chiuderla subito^).
echo.
echo  Le partite sono in: %USERPROFILE%\ak_games
echo  Il log del server:  %USERPROFILE%\ak_games\logs\server.log
echo ============================================
pause
exit /b 0

:FindPython
rem Cerca un Python >= 3.11 ("py -3" prima, poi "python"; l'alias vuoto del
rem Microsoft Store non supera il controllo).
set "PY="
for %%C in ("py -3" "python") do (
    if not defined PY (
        %%~C -c "import sys; sys.exit(sys.version_info < (3, 11))" >nul 2>nul
        if not errorlevel 1 set "PY=%%~C"
    )
)
exit /b 0

:RefreshPath
rem Rilegge il PATH di sistema e utente dal registro, cosi' un programma
rem appena installato con winget si trova subito senza riaprire la finestra.
set "SysPath="
set "UserPath="
for /f "skip=2 tokens=2,*" %%A in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v Path 2^>nul') do set "SysPath=%%B"
for /f "skip=2 tokens=2,*" %%A in ('reg query "HKCU\Environment" /v Path 2^>nul') do set "UserPath=%%B"
if not defined SysPath set "SysPath=%PATH%"
set "PATH=%SysPath%;%UserPath%"
exit /b 0
