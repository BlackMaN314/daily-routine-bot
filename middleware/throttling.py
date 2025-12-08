from typing import Dict
from datetime import datetime
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
import logging

logger = logging.getLogger(__name__)


class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, rate_limit: float = 0.5):
        """
        Middleware для защиты от спама
        
        Args:
            rate_limit: Минимальное время между сообщениями в секундах (по умолчанию 1 секунда)
        """
        self.rate_limit = rate_limit
        self.user_last_message: Dict[int, datetime] = {}
        self.user_warning_count: Dict[int, int] = {}
    
    async def __call__(
        self,
        handler,
        event: TelegramObject,
        data: dict
    ):
        user_id = None
        
        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery) and event.from_user:
            user_id = event.from_user.id
        
        if user_id is None:
            return await handler(event, data)
        
        now = datetime.now()
        
        if user_id in self.user_last_message:
            time_since_last = (now - self.user_last_message[user_id]).total_seconds()
            
            if time_since_last < self.rate_limit:
                wait_time = self.rate_limit - time_since_last
                
                if user_id not in self.user_warning_count:
                    self.user_warning_count[user_id] = 0
                
                self.user_warning_count[user_id] += 1
                
                if self.user_warning_count[user_id] <= 3:
                    if isinstance(event, Message):
                        await event.answer(
                            f"⏳ Слишком много запросов. Подожди {wait_time:.1f} секунд."
                        )
                    elif isinstance(event, CallbackQuery):
                        await event.answer(
                            f"⏳ Подожди {wait_time:.1f} секунд.",
                            show_alert=True
                        )
                elif self.user_warning_count[user_id] > 10:
                    logger.warning(f"Пользователь {user_id} превысил лимит запросов более 10 раз")
                
                return
        
        self.user_last_message[user_id] = now
        
        if user_id in self.user_warning_count and self.user_warning_count[user_id] > 0:
            self.user_warning_count[user_id] = max(0, self.user_warning_count[user_id] - 1)
        
        return await handler(event, data)

