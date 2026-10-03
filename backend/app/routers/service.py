from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import ConfigEntry
from app.schemas import DongleStatus, ServiceStatus
from app.services.pdw_source import check_pdw, pdw_source_instance, PDW_LOG, _log_buffer_lock

router = APIRouter(tags=["service"])


@router.get("/api/service/status", response_model=ServiceStatus)
async def service_status(db: AsyncSession = Depends(get_db)):
    active = pdw_source_instance.is_running if pdw_source_instance is not None else False
    return ServiceStatus(
        active=active,
        frequencies=["PDW (log)"],
        current_freq="PDW",
    )


@router.get("/api/radio/dongle", response_model=DongleStatus)
async def radio_dongle():
    ok, msg = check_pdw()
    return DongleStatus(
        detected=ok,
        message=msg,
        current_freq="PDW",
    )


@router.post("/api/service/restart")
async def service_restart():
    # Sur Windows, le redémarrage est géré hors du process (NSSM/planificateur).
    return {"status": "ignore", "message": "Redémarrage géré par NSSM/le service Windows"}


@router.get("/api/logs")
async def get_logs():
    """Renvoie les dernières lignes du buffer de log PDW."""
    with _log_buffer_lock:
        recent = list(PDW_LOG)[-50:]
    return "\n".join(f"{e['ts']} {e['line']}" for e in recent) or "(vide)"


@router.post("/api/test-discord")
async def test_discord():
    from app.services.notify import send_discord
    from app.database import async_session_factory

    async with async_session_factory() as db:
        wh = await db.get(ConfigEntry, "discord_webhook")
        url = wh.value if wh else ""

    if not url:
        return {"success": False, "message": "Webhook non configur\u00e9"}

    ok, msg = send_discord(
        url, "1234567", "1234567 (TEST)", "0",
        "SAP AVEC OUVERTURE DE PORTE FS001.SERV KOGENHEIM 213 RUE SOLEIL",
        "KOGENHEIM 213 RUE SOLEIL",
        is_urgent=False, is_test=True,
    )
    return {"success": ok, "message": msg}


@router.get("/api/multimon-logs")
async def get_multimon_logs(lines: int = 200):
    """Renvoie les N dernières lignes du buffer de log PDW."""
    with _log_buffer_lock:
        recent = list(PDW_LOG)[-lines:] if lines > 0 else []
    return {
        "lines": recent,
        "count": len(recent),
        "buffer_size": len(PDW_LOG),
    }