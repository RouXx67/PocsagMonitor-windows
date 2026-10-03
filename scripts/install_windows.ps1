# ============================================================
#  Installateur POCSAG Monitor Windows (décodage PDW) - PowerShell
#  ============================================================
#  À lancer en mode Administrateur (clic droit -> Exécuter en tant qu'admin)
#  PowerShell : Set-ExecutionPolicy Bypass -Scope Process
#  puis :  .\scripts\install_windows.ps1
# ============================================================

$ErrorActionPreference = "Stop"

$APP_DIR   = "C:\POCSAGMonitor"
$REPO_URL  = "https://github.com/RouXx67/PocsagMonitor-windows.git"
$PY_URL    = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
$PY_EXE    = "$env:TEMP\python-3.11.9-amd64.exe"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  POCSAG Monitor Windows - Installation automatique"         -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# ------------------------------------------------------------
# 0. Vérification administrateur
# ------------------------------------------------------------
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "[ERREUR] Ce script doit être exécuté en mode Administrateur." -ForegroundColor Red
    Write-Host "         Clic droit sur le script -> Exécuter en tant qu'administrateur"
    exit 1
}

# ------------------------------------------------------------
# 1. Récupération du code
# ------------------------------------------------------------
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "[ERREUR] Git n'est pas installé. Installez-le : https://git-scm.com/download/win" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $APP_DIR)) {
    Write-Host "[1/5] Récupération du code depuis GitHub..." -ForegroundColor Yellow
    git clone $REPO_URL $APP_DIR
} else {
    Write-Host "[1/5] Déjà présent, mise à jour..." -ForegroundColor Yellow
    Push-Location $APP_DIR
    git pull --ff-only
    Pop-Location
}

$backendDir = Join-Path $APP_DIR "backend"
if (-not (Test-Path $backendDir)) { $backendDir = $APP_DIR }
Push-Location $backendDir

# ------------------------------------------------------------
# 2. Python - détection / installation portable
# ------------------------------------------------------------
$PY = "python"
$installed = $false
try {
    $v = & $PY --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[2/5] Python détecté : $v" -ForegroundColor Yellow
        $installed = $true
    }
} catch { }

if (-not $installed) {
    Write-Host "[2/5] Python non trouvé, téléchargement d'une copie portable..." -ForegroundColor Yellow
    if (-not (Test-Path $PY_EXE)) {
        Invoke-WebRequest -Uri $PY_URL -OutFile $PY_EXE
    }
    $PY = Join-Path $APP_DIR "python\python.exe"
    Push-Location $APP_DIR
    Start-Process -Wait -FilePath $PY_EXE -ArgumentList "/quiet", "InstallAllUsers=0", "PrependPath=0", "Include_launcher=0", "TargetDir=$APP_DIR\python"
    Pop-Location
}

# ------------------------------------------------------------
# 3. Environnement virtuel + dépendances
# ------------------------------------------------------------
Write-Host "[3/5] Création de l'environnement virtuel..." -ForegroundColor Yellow
if (-not (Test-Path ".venv")) {
    & $PY -m venv .venv
}

Write-Host "[4/5] Installation des dépendances..." -ForegroundColor Yellow
& ".venv\Scripts\python.exe" -m pip install --upgrade pip | Out-Null
& ".venv\Scripts\python.exe" -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERREUR] Échec de l'installation des dépendances." -ForegroundColor Red
    exit 1
}

# ------------------------------------------------------------
# 5. NSSM - service optionnel
# ------------------------------------------------------------
Write-Host "[5/5] Configuration" -ForegroundColor Yellow
if (Get-Command nssm -ErrorAction SilentlyContinue) {
    $answer = Read-Host "Installer comme service Windows (NSSM) ? [o/N]"
    if ($answer -match "^[oO]$") {
        $SVC = "POCSAG-Monitor"
        nssm stop $SVC | Out-Null
        nssm remove $SVC confirm | Out-Null
        nssm install $SVC "$backendDir\.venv\Scripts\python.exe" "-m uvicorn app.main:app --host 0.0.0.0 --port 8080"
        nssm set $SVC AppDirectory "$backendDir"
        nssm set $SVC Description "POCSAG Monitor Windows (PDW) - Interface web + notifications"
        nssm set $SVC DisplayName "POCSAG Monitor Windows"
        nssm set $SVC Start SERVICE_AUTO_START
        nssm start $SVC
        Write-Host "Service installé et démarré." -ForegroundColor Green
    }
} else {
    Write-Host "NSSM non trouvé (optionnel). Lecture via run_windows.bat pour un démarrage manuel." -ForegroundColor DarkGray
}

# ------------------------------------------------------------
# Fin
# ------------------------------------------------------------
Pop-Location
Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  Installation terminée !"                                    -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Démarrage manuel : $APP_DIR\scripts\run_windows.bat"
Write-Host "  Interface web    : http://localhost:8080"
Write-Host "                     (réseau : http://IP-DE-LA-VM:8080)"
Write-Host ""
Write-Host "  IMPORTANT : SDR# + Virtual Audio Cable + PDW doivent décoder"
Write-Host "  et écrire leur log dans C:\PDW (fichier YYMMDD.log)."
Write-Host ""
Write-Host "  Mot de passe admin par défaut : admin (à changer dans Paramètres)"
Write-Host ""
Read-Host "Appuyez sur Entrée pour fermer"