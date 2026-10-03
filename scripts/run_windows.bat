@echo off
REM Lance le backend POCSAG Monitor Windows (décodage PDW)
cd /d "%~dp0..\backend"

REM Utiliser le .venv s'il existe
set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

REM Créer le dossier data s'il n'existe pas
if not exist "data" mkdir "data"

set "LOG=%~dp0..\server.log"

echo [POCSAG-Win] Démarrage du serveur sur http://0.0.0.0:8080
echo [POCSAG-Win] Log : %LOG%
echo [POCSAG-Win] Arrêtez avec Ctrl+C
echo.

"%PY%" -c "import uvicorn, fastapi, sqlalchemy, aiosqlite, pydantic_settings, jose, requests" >nul 2>&1
if errorlevel 1 (
    echo [POCSAG-Win] !!! Dépendances manquantes. Lancez d'abord :
    echo            scripts\install_windows.bat
    pause
    exit /b 1
)

echo [POCSAG-Win] Démarrage uvicorn...
"%PY%" -m uvicorn app.main:app --host 0.0.0.0 --port 8080 > %LOG% 2>&1
echo.
echo [POCSAG-Win] Le serveur s'est arrêté (code %errorlevel%).
echo [POCSAG-Win] Détails dans %LOG%
pause