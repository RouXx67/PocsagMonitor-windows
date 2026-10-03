@echo off
REM ============================================================
REM  Installateur POCSAG Monitor Windows (décodage PDW)
REM  ------------------------------------------------------------
REM  Ce script :
REM    1. Crée l'arborescence du projet
REM    2. Récupère le code depuis GitHub (si absent)
REM    3. Installe Python 3.11+ de façon portable (si nécessaire)
REM    4. Crée un environnement virtuel et installe les dépendances
REM    5. Prépare l'autodémarrage avec NSSM (si installé)
REM  ------------------------------------------------------------
REM  Lancez en mode Administrateur : clic droit -> Exécuter en tant qu'admin
REM ============================================================
@setlocal enabledelayedexpansion

set "APP_DIR=C:\POCSAGMonitor"
set "REPO_URL=https://github.com/RouXx67/PocsagMonitor-windows.git"
set "PY_URL=https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
set "PY_INSTALLER=%TEMP%\python-3.11.9-amd64.exe"

echo.
echo  ============================================================
echo    POCSAG Monitor Windows - Installation automatique
echo  ============================================================
echo.

REM ------------------------------------------------------------
REM 0. Vérification mode administrateur
REM ------------------------------------------------------------
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo.
    echo  [ERREUR] Ce script doit etre lance en mode Administrateur.
    echo           Clic droit sur le script -^> "Executer en tant qu'administrateur"
    echo.
    pause
    exit /b 1
)

REM ------------------------------------------------------------
REM 1. Utilisation de Git si disponible (optionnel)
REM ------------------------------------------------------------
where git >nul 2>&1
if %errorLevel% equ 0 (set "HAS_GIT=1") else (set "HAS_GIT=0")

if not exist "%APP_DIR%" (
    echo  [1/5] Recuperation du code depuis GitHub...
    if "%HAS_GIT%"=="1" (
        git clone %REPO_URL% "%APP_DIR%"
    ) else (
        echo  [ERREUR] Git n'est pas installe. Installez Git d'abord:
        echo          https://git-scm.com/download/win
        pause
        exit /b 1
    )
) else (
    echo  [1/5] Dossier %APP_DIR% deja present, mise a jour...
    cd /d "%APP_DIR%"
    if "%HAS_GIT%"=="1" (git pull --ff-only)
)

cd /d "%APP_DIR%\backend"

REM ------------------------------------------------------------
REM 2. Python - détection
REM ------------------------------------------------------------
set "PYTHON_EXE=python"
where python >nul 2>&1
if %errorLevel% equ 0 (
    for /f "delims=" %%v in ('python --version 2^>^&1') do set "PYVER=%%v"
    echo  [2/5] Python detecte : !PYVER!
    set "INSTALLED_PY=1"
) else (
    echo  [2/5] Python non detecte, telechargement portable...
    echo        (Copie de Python 3.11.9 dans %APP_DIR%\python)
    if not exist "%PY_INSTALLER%" (
        powershell -Command "Invoke-WebRequest -Uri '%PY_URL%' -OutFile '%PY_INSTALLER%'"
        if errorlevel 1 (
            echo  [ERREUR] Echec du telechargement de Python.
            pause
            exit /b 1
        )
    )
    echo        Installation silencieuse de Python dans %APP_DIR%\python...
    "%PY_INSTALLER%" /quiet InstallAllUsers=0 PrependPath=0 Include_launcher=0 TargetDir="%APP_DIR%\python"
    set "PYTHON_EXE=%APP_DIR%\python\python.exe"
    set "INSTALLED_PY=0"
)

REM ------------------------------------------------------------
REM 3. Environnement virtuel + dépendances
REM ------------------------------------------------------------
echo  [3/5] Creation de l'environnement virtuel...
if not exist ".venv" (
    "%PYTHON_EXE%" -m venv .venv
)

echo  [4/5] Installation des dependances...
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul 2>&1
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo  [ERREUR] Echec de l'installation des dependances.
    pause
    exit /b 1
)

REM ------------------------------------------------------------
REM 4. Vérification de la base de données (créée au premier run)
REM ------------------------------------------------------------
echo  [5/5] Test de demarrage rapide (3 sec)...
start "" /b ".venv\Scripts\python.exe" -c "import uvicorn; print('OK: uvicorn importe')"
timeout /t 2 >nul

REM ------------------------------------------------------------
REM 5. Proposition autodémarrage NSSM (optionnel)
REM ------------------------------------------------------------
where nssm >nul 2>&1
if %errorLevel% equ 0 (
    echo.
    set /p INSTALL_SERVICE="Voulez-vous installer comme service Windows (NSSM) ? [o/N] : "
    if /i "!INSTALL_SERVICE!"=="o" (
        set "SVC_NAME=POCSAG-Monitor"
        nssm stop %SVC_NAME% >nul 2>&1
        nssm remove %SVC_NAME% confirm >nul 2>&1
        nssm install %SVC_NAME% "%APP_DIR%\backend\.venv\Scripts\python.exe" "-m uvicorn app.main:app --host 0.0.0.0 --port 8080"
        nssm set %SVC_NAME% AppDirectory "%APP_DIR%\backend"
        nssm set %SVC_NAME% Description "POCSAG Monitor Windows (PDW) - Interface web + notifications"
        nssm set %SVC_NAME% DisplayName "POCSAG Monitor Windows"
        nssm set %SVC_NAME% Start SERVICE_AUTO_START
        nssm start %SVC_NAME%
        echo.
        echo  Service installe et demarre.
    )
)

echo.
echo  ============================================================
echo    Installation terminee !
echo  ============================================================
echo.
echo  Pour demarrer manuellement :
echo     "%APP_DIR%\scripts\run_windows.bat"
echo.
echo  Ensuite ouvrez :  http://localhost:8080
echo  (accessible depuis le reseau : http://IP-DE-LA-VM:8080)
echo.
echo  IMPORTANT : SDR# + Virtual Audio Cable + PDW doivent decoder
echo  et ecrire leur log dans C:\PDW (fichier YYMMDD.log).
echo.
echo  Mot de passe admin par defaut : admin  (a changer dans l'onglet Parametres)
echo.
pause