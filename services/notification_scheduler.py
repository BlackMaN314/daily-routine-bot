import logging
import asyncio
from datetime import datetime, timedelta
import pytz
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from services.api import api
from services.token_storage import token_storage

logger = logging.getLogger(__name__)


class NotificationScheduler:
    def __init__(self, bot: Bot, check_interval: int = 10):
        self.bot = bot
        self.check_interval = check_interval
        self.running = False
        self.last_sent_notifications = {}
    
    async def start(self):
        self.running = True
        asyncio.create_task(self._scheduler_loop())
    
    async def stop(self):
        self.running = False
    
    def _get_seconds_until_next_minute(self) -> float:
        now = datetime.now()
        next_minute = (now.replace(second=0, microsecond=0) + timedelta(minutes=1))
        delta = (next_minute - now).total_seconds()
        return max(0.1, delta)
    
    async def _scheduler_loop(self):
        while self.running:
            try:
                await self._check_and_send_notifications()
            except Exception as e:
                logger.error(f"Ошибка в цикле планировщика: {e}", exc_info=True)
                await asyncio.sleep(5)
            
            sleep_time = self._get_seconds_until_next_minute()
            await asyncio.sleep(sleep_time)
    
    async def _check_and_send_notifications(self):
        try:
            telegram_ids = await token_storage.get_all_telegram_ids()
            
            if not telegram_ids:
                return
            
            for telegram_id in telegram_ids:
                try:
                    await self._check_user_notifications(telegram_id)
                except Exception as e:
                    logger.error(f"Ошибка при проверке уведомлений для пользователя {telegram_id}: {e}", exc_info=True)
                    continue
                    
        except Exception as e:
            logger.error(f"Ошибка при проверке уведомлений: {e}", exc_info=True)
    
    async def _check_user_notifications(self, telegram_id: int):
        try:
            user_data = await token_storage.get_user_data(telegram_id)
            
            if not user_data:
                try:
                    chat = await self.bot.get_chat(telegram_id)
                    user_data = {
                        "username": chat.username,
                        "first_name": chat.first_name,
                        "last_name": chat.last_name,
                        "photo_url": None
                    }
                except Exception as e:
                    logger.error(f"Не удалось получить данные пользователя {telegram_id} из Telegram API: {e}")
                    return
            
            settings = None
            try:
                settings_data = await api.get("/telegram/settings", params={
                    "telegram_id": telegram_id,
                    "username": user_data.get("username"),
                    "first_name": user_data.get("first_name"),
                    "last_name": user_data.get("last_name"),
                    "photo_url": user_data.get("photo_url")
                })
                settings = settings_data.get("settings", {})
            except Exception as e:
                error_msg = str(e)
                if "401" in error_msg or "Unauthorized" in error_msg:
                    try:
                        from utils.helpers import get_user_photo_url
                        photo_url = await get_user_photo_url(self.bot, telegram_id)
                        auth_data = await api.register_telegram_user(
                            telegram_id=telegram_id,
                            username=user_data.get("username"),
                            first_name=user_data.get("first_name"),
                            last_name=user_data.get("last_name"),
                            photo_url=photo_url
                        )
                        tokens = auth_data.get("tokens", {})
                        access_token = tokens.get("access_token")
                        refresh_token = tokens.get("refresh_token")
                        user_id = auth_data.get("user", {}).get("id")
                        
                        if access_token and refresh_token:
                            await token_storage.save_tokens(
                                telegram_id=telegram_id,
                                access_token=access_token,
                                refresh_token=refresh_token,
                                user_id=user_id,
                                username=user_data.get("username"),
                                first_name=user_data.get("first_name"),
                                last_name=user_data.get("last_name"),
                                photo_url=photo_url
                            )
                            
                            try:
                                settings_data = await api.get("/telegram/settings", params={
                                    "telegram_id": telegram_id,
                                    "username": user_data.get("username"),
                                    "first_name": user_data.get("first_name"),
                                    "last_name": user_data.get("last_name"),
                                    "photo_url": photo_url
                                })
                                settings = settings_data.get("settings", {})
                            except Exception as settings_error:
                                logger.error(f"Пользователь {telegram_id}: не удалось получить настройки после перерегистрации: {settings_error}", exc_info=True)
                                return
                        else:
                            logger.error(f"Пользователь {telegram_id}: не удалось получить токены при перерегистрации")
                            return
                    except Exception as reg_error:
                        logger.error(f"Пользователь {telegram_id}: ошибка при перерегистрации: {reg_error}", exc_info=True)
                        return
                else:
                    logger.error(f"Не удалось получить настройки для пользователя {telegram_id}: {e}", exc_info=True)
                    return
            
            if settings is None:
                return
            
            if settings.get("dnd_enabled", False):
                return
            
            notify_times = settings.get("notify_times", [])
            if not notify_times:
                return
            
            timezone_str = settings.get("timezone", "UTC")
            try:
                user_tz = pytz.timezone(timezone_str)
            except pytz.exceptions.UnknownTimeZoneError:
                logger.warning(f"Неизвестный часовой пояс {timezone_str} для пользователя {telegram_id}, используем UTC")
                user_tz = pytz.UTC
            
            utc_now = datetime.now(pytz.UTC)
            user_time = utc_now.astimezone(user_tz)
            current_time_str = user_time.strftime("%H:%M")
            current_date = user_time.date()
            
            if current_time_str not in notify_times:
                return
            
            last_sent = self.last_sent_notifications.get(telegram_id, {})
            last_sent_date = last_sent.get(current_time_str)
            
            if last_sent_date == current_date:
                return
            
            if last_sent_date and last_sent_date < current_date:
                self.last_sent_notifications[telegram_id] = {}
            
            try:
                habits_data = await api.get("/habits/today", params={
                    "telegram_id": telegram_id,
                    "username": user_data.get("username"),
                    "first_name": user_data.get("first_name"),
                    "last_name": user_data.get("last_name"),
                    "photo_url": user_data.get("photo_url")
                })
                habits = habits_data.get("habits", [])
            except Exception as e:
                logger.error(f"Не удалось получить привычки для пользователя {telegram_id}: {e}", exc_info=True)
                return
            
            if not habits:
                return
            
            await self._send_habits_notification(telegram_id, habits)
            
            if telegram_id not in self.last_sent_notifications:
                self.last_sent_notifications[telegram_id] = {}
            self.last_sent_notifications[telegram_id][current_time_str] = current_date
            
        except Exception as e:
            logger.error(f"Ошибка при проверке уведомлений для пользователя {telegram_id}: {e}", exc_info=True)
    
    async def _send_habits_notification(self, telegram_id: int, habits: list):
        try:
            message = self._format_habits_message(habits)
            keyboard = self._create_habits_keyboard(habits)
            
            await self.bot.send_message(
                chat_id=telegram_id,
                text=message,
                reply_markup=keyboard
            )
            
        except TelegramForbiddenError:
            pass
        except TelegramBadRequest as e:
            logger.error(f"Ошибка Telegram API при отправке напоминания пользователю {telegram_id}: {e}")
        except Exception as e:
            logger.error(f"Ошибка при отправке напоминания пользователю {telegram_id}: {e}", exc_info=True)
    
    def _format_habits_message(self, habits: list) -> str:
        text = "⏰ Напоминание о привычках:\n\n"
        
        completed_habits = [h for h in habits if h.get("completed", False)]
        pending_habits = [h for h in habits if not h.get("completed", False)]
        
        if pending_habits:
            for habit in pending_habits:
                emoji = habit.get("emoji", "📌")
                title = habit.get("name", "Привычка")
                goal = habit.get("goal", 0)
                unit = habit.get("unit", "")
                
                if unit:
                    text += f"{emoji} {title} — {goal} {unit}\n"
                else:
                    text += f"{emoji} {title}\n"
        
        if completed_habits:
            if pending_habits:
                text += "\n"
            text += "✅ Выполнено:\n"
            for habit in completed_habits:
                emoji = habit.get("emoji", "📌")
                title = habit.get("name", "Привычка")
                text += f"✅ {emoji} {title}\n"
        
        text += "\n💪 Ты справишься!"
        
        return text
    
    def _create_habits_keyboard(self, habits: list) -> InlineKeyboardMarkup:
        keyboard = []
        
        keyboard.append([
            InlineKeyboardButton(text="📋 Открыть список", callback_data="back_today")
        ])
        
        if habits:
            keyboard.append([
                InlineKeyboardButton(text="✅ Отметить все выполненными", callback_data="morning_complete_all")
            ])
        
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
