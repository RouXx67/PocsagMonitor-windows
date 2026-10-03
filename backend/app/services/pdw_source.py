from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.config import settings

log = logging.getLogger("pocsag.pdw")

# Buffer circulaire pour les logs du fichier PDW
PDW_LOG: deque[dict[str, str]] = deque(maxlen=500)
_log_buffer_lock = threading.Lock()


def _add_to_log_buffer(line: str):
    with _log_buffer_lock:
        PDW_LOG.append({
            "ts": datetime.now().isoformat(timespec="seconds"),
            "source": "pdw",
            "line": line.rstrip("\n"),
        })


def _current_logfile() -> Path:
    """Chemin du fichier de log PDW du jour (ex. C:\\PDW\\261003.log)."""
    fname = datetime.now().strftime(settings.pdw_log_pattern)
    return Path(settings.pdw_log_dir) / fname


def _state_file() -> Path:
    """Fichier d'état pour mémoriser la dernière position lue par fichier."""
    return settings.data_dir / ".pdw_state.json"


def _load_state() -> dict[str, int]:
    import json
    try:
        p = _state_file()
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_state(state: dict[str, int]):
    import json
    try:
        p = _state_file()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        log.error("[PDW] Sauvegarde état impossible: %s", e)


def parse_pdw_line(line: str) -> Optional[dict]:
    """Transpose une ligne PDW vers {ric, func, message, raw_line}.

    Format réel d'une ligne PDW (colonnes séparées par des espaces/tabulations) :
        0678960 03:44:22 03-10-26 POCSAG-2  ALPHA   512  SAP AVEC OUVERTURE DE PORTE ...

    - 1er champ  : RIC (longueur variable, typiquement 6-7 chiffres)
    - 2e champ   : heure          (ignoré)
    - 3e champ   : date           (ignoré)
    - 4e champ   : protocole POCSAG-X (ignoré)
    - 5e champ   : type (ALPHA/NUMERIC/TONE) — ignoré
    - 6e champ   : baud rate (512/1200/2400) — ignoré
    - tout après : le message

    PDW n'expose pas la 'Function' POCSAG ; on utilise donc func='0'.
    RIC : on accepte une longueur variable (au moins 3 chiffres).
    """
    if not line or not line.strip():
        return None

    # Retire un éventuel BOM UTF-8 et normalise les séparateurs
    line = line.lstrip("\ufeff").strip()
    parts = line.split()
    # Minimum : RIC + au moins quelques colonnes
    if len(parts) < 6:
        return None

    ric = parts[0]
    if not ric.isdigit() or len(ric) < 3:
        return None

    message = parts[6:]  # tout ce qui suit le champ baud rate
    msg_text = " ".join(message).strip()

    return {
        "ric": ric,
        "func": "0",
        "message": msg_text,
        "raw_line": line.rstrip("\n"),
    }


class PdwSource:
    """Lit en continu le fichier de log PDW et alimente le gestionnaire
    on_message (stockage + notifications). Équivalent Windows de RadioScanner."""

    def __init__(self, on_message):
        self.on_message = on_message
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def set_loop(self, loop):
        self._loop = loop

    def start(self):
        if self.is_running:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="pdw-reader")
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _call_on_message(self, parsed):
        if self._loop is None or self.on_message is None:
            return
        try:
            asyncio.run_coroutine_threadsafe(self.on_message(parsed), self._loop)
        except Exception:
            pass

    def _run(self):
        log.info("[PDW] Démarrage de la lecture du log PDW (répertoire: %s)", settings.pdw_log_dir)
        state = _load_state()
        last_file = None
        position = 0

        while not self._stop.is_set():
            try:
                path = _current_logfile()

                # Bascule de fichier (nouveau jour) → on suit depuis 0 sans re-traiter
                if last_file is not None and path.name != last_file:
                    log.info("[PDW] Nouveau fichier de log détecté : %s", path.name)
                    position = 0
                    last_file = None

                if path.exists():
                    current_size = path.stat().st_size
                    # Repart de la position mémorisée pour ce fichier si déjà connu
                    if last_file is None:
                        position = state.get(path.name, 0)
                        # Si le fichier a été tronqué (position > taille), on repart de 0
                        if position > current_size:
                            position = 0
                        log.info("[PDW] Lecture de %s à partir de l'offset %d (taille %d)",
                                 path.name, position, current_size)

                    if current_size >= position:
                        new_pos = position
                        with open(path, "r", encoding="utf-8", errors="replace") as f:
                            f.seek(position)
                            for line in f:
                                if self._stop.is_set():
                                    break
                                line = line.rstrip("\n")
                                if not line:
                                    continue
                                _add_to_log_buffer(line)
                                parsed = parse_pdw_line(line)
                                if parsed:
                                    self._call_on_message(parsed)
                            new_pos = f.tell()
                        state[path.name] = new_pos
                        _save_state(state)
                        position = new_pos
                        last_file = path.name
                elif last_file is not None and not path.exists():
                    # Fichier du jour pas encore créé → on reste prêt
                    pass

            except Exception as e:
                log.error("[PDW] Erreur de lecture: %s", e)

            # Attend l'intervalle de polling avant de relire le fichier
            self._stop.wait(settings.pdw_poll_interval)


# Instance globale, définie par main.py pour que les routes puissent le consulter.
pdw_source_instance: Optional["PdwSource"] = None


def check_pdw() -> tuple[bool, str]:
    """Vérifie que le répertoire / le fichier de log PDW existe."""
    path = _current_logfile()
    if not Path(settings.pdw_log_dir).exists():
        return False, f"Répertoire {settings.pdw_log_dir} introuvable"
    if path.exists():
        return True, f"Fichier de log PDW présent : {path.name}"
    return True, f"Répertoire OK, en attente du fichier {path.name}"