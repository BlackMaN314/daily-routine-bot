import asyncio
import os
import aiosqlite
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def init_database():
    db_path = "data/tokens.db"
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    async with aiosqlite.connect(db_path) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS tokens (
                telegram_id INTEGER PRIMARY KEY,
                access_token TEXT,
                refresh_token TEXT,
                user_id INTEGER,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                photo_url TEXT
            )
        ''')
        await db.commit()
    
    logger.info(f"База данных SQLite готова: {db_path}")


if __name__ == "__main__":
    asyncio.run(init_database())

