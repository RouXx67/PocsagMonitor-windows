# POCSAG Monitor Windows (décodage PDW)

Interface web + notifications pour le décodage POCSAG **sans multimon-ng**.
Cette version **Windows** lit directement le **fichier de log de PDW** (Paging
Decoder for Windows) au lieu d'utiliser rtl_fm/multimon-ng.

- Backend : **FastAPI + Python** (portable, identique au projet Linux)
- Décodage : **PDW** (via SDR# + Virtual Audio Cable)
- Réglages radio (fréquence/gain) : faits dans **SDR#**, pas dans cette appli
- Notifications : **Discord** et **Telegram**

## Architecture

```
Dongle RTL-SDR
   │
   ▼
SDR# / SDR++   (réglage fréquence + gain)
   │  audio via Virtual Audio Cable
   ▼
PDW            (décodage POCSAG)
   │  écrit un fichier de log par jour : C:\PDW\YYMMDD.log
   ▼
Backend FastAPI (pood_reads le fichier du jour en continu)
   │  → parser → base SQLite locale → notifications
   ▼
Page web (http://<IP-VM>:8080)
```

## Prérequis (sur la VM Windows)

1. **Python 3.11+** ([python.org](https://python.org), cocher "Add to PATH")
2. **SDR#** ou **SDR++** + driver RTL-SDR (`Zadig`)
3. **Virtual Audio Cable** ([VB-Audio](https://vb-audio.com/Cable/))
4. **PDW** ([Paging Decoder for Windows](https://github.com/AllanPrinse/pdw))
   - Taguer l'entrée audio sur le cable virtuel
   - Activer l'écriture du **log file** dans `C:\PDW` (format `YYMMDD.log`)

## Installation

```bat
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Lancement

```bat
scripts\run_windows.bat
```

Puis ouvrez `http://localhost:8080` (ou `http://<IP-VM>:8080` depuis le réseau).

Pour un démarrage automatique au boot, installez comme service avec
[NSSM](https://nssm.cc/):

```bat
nssm install POCSAG-Win "C:\Program Files\Python311\python.exe" "-m uvicorn app.main:app --host 0.0.0.0 --port 8080"
nssm set POCSAG-Win AppDirectory "C:\chemin\vers\backend"
nssm start POCSAG-Win
```

> **Important** : le service doit démarrer APRÈS PDW (le lecteur attend le
> fichier de log du jour, il bascule tout seul à minuit).

## Configuration

- Mot de passe admin par défaut : `admin` (à changer dans l'onglet Paramètres)
- Webhook Discord + Telegram : onglet **Paramètres** → **Notifications**
- Mots-clés d'urgence : séparés par des virgules (ex. `AVP,FEU,RENFORT`)
- Blacklist : permet d'ignorer certains RIC

## Format du log PDW reconnu

Les lignes du fichier `YYMMDD.log` sont du format :

```
0678960 03:44:22 03-10-26 POCSAG-2  ALPHA   512  SAP AVEC OUVERTURE DE PORTE ...
{RIC}   {heure}  {date}   {proto}   {type} {baud} ............ message ........
```

Le parseur (dans `backend/app/services/pdw_source.py`, fonction `parse_pdw_line`)
lit le **RIC** (1er champ) et **tout ce qui suit le champ `baud`** comme message.
La sous-adresse POCSAG n'étant pas exposée par PDW, elle est fixée à `0`.