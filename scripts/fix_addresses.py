# ============================================================
#  Recalcule les adresses des messages existants et refait la géolocalisation.
#  Usage :  python scripts/fix_addresses.py
# ============================================================
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from sqlalchemy import select

from app.database import async_session_factory
from app.models import Message
from app.services.address import extract_address


async def main():
    async with async_session_factory() as db:
        rows = (await db.execute(select(Message).order_by(Message.id))).scalars().all()
        fixed = 0
        for m in rows:
            if not m.message:
                continue
            addr = extract_address(m.message)
            if addr != (m.address or ""):
                m.address = addr or None
                fixed += 1
        await db.commit()
        print(f"{fixed} message(s) mis à jour sur {len(rows)} au total")


if __name__ == "__main__":
    asyncio.run(main())