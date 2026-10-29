"""python -m scripts.sync_1c_references: atomic GET-only 1C reference sync."""
import asyncio
import json
from app.db.session import async_session_maker, engine
from app.services.onec_service import sync_references


async def main():
    try:
        async with async_session_maker() as db:
            result = await sync_references(db)
            print(json.dumps(result, ensure_ascii=True, indent=2))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
