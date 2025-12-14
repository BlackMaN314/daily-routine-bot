import logging
import os
from typing import Optional, Dict
import aiosqlite

logger = logging.getLogger(__name__)


class TokenStorage:
    def __init__(self, db_path: str = "data/tokens.db", bot_id: int = 0):
        self.db_path = db_path
        self.bot_id = bot_id
        self._initialized = False
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        logger.info(f"Хранение токенов: SQLite ({self.db_path})")

    async def _init_db(self):
        if self._initialized:
            return
        
        async with aiosqlite.connect(self.db_path) as db:
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
            self._initialized = True

    async def _get_tokens_data(self, telegram_id: int) -> Optional[Dict]:
        """Получить данные токенов из базы данных"""
        await self._init_db()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT access_token, refresh_token, user_id, username, first_name, last_name, photo_url FROM tokens WHERE telegram_id = ?",
                (telegram_id,)
            )
            row = await cursor.fetchone()
            if row:
                tokens_data = {
                    "access_token": row[0],
                    "refresh_token": row[1],
                    "user_id": row[2],
                    "username": row[3],
                    "first_name": row[4],
                    "last_name": row[5],
                    "photo_url": row[6]
                }
                logger.debug(f"Токены найдены в БД для telegram_id={telegram_id}, access_token={'есть' if tokens_data['access_token'] else 'нет'}")
                return tokens_data
        logger.debug(f"Токены не найдены в БД для telegram_id={telegram_id}")
        return None

    async def _save_tokens_data(self, telegram_id: int, tokens_data: Dict):
        """Сохранить данные токенов в базу данных"""
        await self._init_db()
        async with aiosqlite.connect(self.db_path) as db:
            access_token = tokens_data.get("access_token")
            refresh_token = tokens_data.get("refresh_token")
            user_id = tokens_data.get("user_id")
            
            if not access_token or not refresh_token:
                logger.warning(f"Попытка сохранить неполные токены для telegram_id={telegram_id}")
            
            await db.execute('''
                INSERT OR REPLACE INTO tokens
                (telegram_id, access_token, refresh_token, user_id, username, first_name, last_name, photo_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                telegram_id,
                access_token,
                refresh_token,
                user_id,
                tokens_data.get("username"),
                tokens_data.get("first_name"),
                tokens_data.get("last_name"),
                tokens_data.get("photo_url")
            ))
            await db.commit()
            logger.info(f"Токены сохранены в БД для telegram_id={telegram_id}, user_id={user_id}")

    async def save_tokens(self, telegram_id: int, access_token: str, refresh_token: str, user_id: Optional[int] = None,
                    username: Optional[str] = None, first_name: Optional[str] = None, last_name: Optional[str] = None,
                    photo_url: Optional[str] = None):
        tokens_data = await self._get_tokens_data(telegram_id) or {}

        tokens_data.update({
            "access_token": access_token,
            "refresh_token": refresh_token,
            "user_id": user_id
        })

        if username is not None:
            tokens_data["username"] = username
        if first_name is not None:
            tokens_data["first_name"] = first_name
        if last_name is not None:
            tokens_data["last_name"] = last_name
        if photo_url is not None:
            tokens_data["photo_url"] = photo_url

        await self._save_tokens_data(telegram_id, tokens_data)

    async def get_user_data(self, telegram_id: int) -> Dict[str, Optional[str]]:
        tokens = await self.get_tokens(telegram_id)
        if not tokens:
            return {}
        return {
            "username": tokens.get("username"),
            "first_name": tokens.get("first_name"),
            "last_name": tokens.get("last_name"),
            "photo_url": tokens.get("photo_url")
        }

    async def get_tokens(self, telegram_id: int) -> Optional[Dict[str, str]]:
        return await self._get_tokens_data(telegram_id)

    async def get_access_token(self, telegram_id: int) -> Optional[str]:
        tokens = await self.get_tokens(telegram_id)
        return tokens.get("access_token") if tokens else None

    async def get_refresh_token(self, telegram_id: int) -> Optional[str]:
        tokens = await self.get_tokens(telegram_id)
        return tokens.get("refresh_token") if tokens else None

    async def get_user_id(self, telegram_id: int) -> Optional[int]:
        tokens = await self.get_tokens(telegram_id)
        user_id = tokens.get("user_id") if tokens else None
        return int(user_id) if user_id is not None else None

    async def update_access_token(self, telegram_id: int, access_token: str):
        tokens_data = await self._get_tokens_data(telegram_id)
        if tokens_data:
            tokens_data["access_token"] = access_token
            await self._save_tokens_data(telegram_id, tokens_data)
            logger.info(f"Access token обновлен в хранилище для telegram_id={telegram_id}")
        else:
            logger.warning(f"Не удалось обновить access token для telegram_id={telegram_id}: токены не найдены в БД")

    async def update_tokens(self, telegram_id: int, access_token: str, refresh_token: str):
        tokens_data = await self._get_tokens_data(telegram_id)
        if tokens_data:
            tokens_data["access_token"] = access_token
            tokens_data["refresh_token"] = refresh_token
            await self._save_tokens_data(telegram_id, tokens_data)

    async def get_all_telegram_ids(self) -> list[int]:
        """Получить список всех telegram_id из базы данных"""
        await self._init_db()
        telegram_ids = []
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT telegram_id FROM tokens")
            rows = await cursor.fetchall()
            for row in rows:
                telegram_ids.append(row[0])
        return telegram_ids


token_storage = TokenStorage()
