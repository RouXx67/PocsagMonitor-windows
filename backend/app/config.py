from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "POCSAG Monitor Win"
    version: str = "1.0.0"

    host: str = "0.0.0.0"
    port: int = 8080

    # Base locale SQLite (créée automatiquement)
    db_name: str = "pocsag_win.db"
    base_dir: Path = Path(os.path.dirname(os.path.abspath(__file__)))
    data_dir: Path = base_dir / ".." / "data"

    log_file: str = ""
    log_level: str = "INFO"

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    admin_password_default: str = "admin"

    # Décodage : cette version Windows lit le log de PDW (pas multimon/multimon).
    decoder: str = "pdw"
    pdw_log_dir: str = r"C:\PDW"
    pdw_log_pattern: str = "%y%m%d.log"
    pdw_poll_interval: float = 0.5

    default_keywords: list[str] = [
        "AVP", "FEU", "DESINCARCERATION", "RENFORT", "URGENT"
    ]

    geo_timeout: int = 3
    log_max_entries: int = 300

    model_config = {"env_prefix": "POCSAG_"}

    @property
    def db_url(self) -> str:
        return f"sqlite+aiosqlite:///{self.data_dir / self.db_name}"


settings = Settings()