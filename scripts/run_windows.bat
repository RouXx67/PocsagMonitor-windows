@echo off
REM Lance le backend POCSAG Monitor Windows (décodage PDW)
REM Nécessite Python 3.11+ installé et requirements installés.
cd /d "%~dp0..\backend"

echo [POCSAG-Win] Démarrage du serveur sur http://0.0.0.0:8080
echo [POCSAG-Win] Arrêtez avec Ctrl+C

python -m uvicorn app.main:app --host 0.0.0.0 --port 8080
if errorlevel 1 (
    echo.
    echo [POCSAG-Win] Erreur au démarrage. Vérifiez que Python est installé et
    echo que les dépendances sont présentes : pip install -r requirements.txt
    pause
)