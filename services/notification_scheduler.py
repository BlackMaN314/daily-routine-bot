import logging
import asyncio
from datetime import datetime
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from services.api import api
from services.token_storage import token_storage

logger = logging.getLogger(__name__)


class NotificationScheduler:
    def __init__(self, bot: Bot, check_interval: int = 10):
        """
        Планировщик уведомлений о привычках
        
        Args:
            bot: Экземпляр бота
            check_interval: Интервал проверки времени в секундах (по умолчанию 10)
        """
        self.bot = bot
        self.check_interval = check_interval
        self.running = False
        self.last_sent_notifications = {}  # {telegram_id: {time: datetime}}
    
    async def start(self):
        """Запуск планировщика"""
        self.running = True
        logger.info("Планировщик уведомлений запущен")
        asyncio.create_task(self._scheduler_loop())
    
    async def stop(self):
        """Остановка планировщика"""
        self.running = False
        logger.info("Планировщик уведомлений остановлен")
    
    async def _scheduler_loop(self):
        """Основной цикл планировщика"""
        while self.running:
            try:
                await self._check_and_send_notifications()
            except Exception as e:
                logger.error(f"Ошибка в цикле планировщика: {e}", exc_info=True)
                # Небольшая задержка при ошибке, чтобы не перегружать систему
                await asyncio.sleep(5)
            
            await asyncio.sleep(self.check_interval)
    
    async def _check_and_send_notifications(self):
        """Проверка времени и отправка уведомлений"""
        try:
            # Получаем всех пользователей
            telegram_ids = await token_storage.get_all_telegram_ids()
            
            if not telegram_ids:
                logger.debug("Нет пользователей для проверки уведомлений")
                return
            
            current_time = datetime.now()
            current_time_str = current_time.strftime("%H:%M")
            current_second = current_time.second
            
            logger.debug(f"Проверка уведомлений: время={current_time_str}, секунда={current_second}, пользователей={len(telegram_ids)}")
            
            # Проверяем время только в начале минуты (первые 10 секунд) для точности
            # Это позволяет отправлять уведомления в нужное время, а не с задержкой до минуты
            if current_second > 10:
                return
            
            for telegram_id in telegram_ids:
                try:
                    await self._check_user_notifications(telegram_id, current_time_str, current_time)
                except Exception as e:
                    logger.error(f"Ошибка при проверке уведомлений для пользователя {telegram_id}: {e}", exc_info=True)
                    continue
                    
        except Exception as e:
            logger.error(f"Ошибка при проверке уведомлений: {e}", exc_info=True)
    
    async def _check_user_notifications(self, telegram_id: int, current_time_str: str, current_time: datetime):
        """Проверка и отправка уведомлений для конкретного пользователя"""
        try:
            # Получаем данные пользователя из хранилища
            user_data = await token_storage.get_user_data(telegram_id)
            if not user_data:
                logger.debug(f"Пользователь {telegram_id}: нет данных в хранилище")
                return
            
            # Получаем настройки из бэкенда
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
                logger.warning(f"Не удалось получить настройки для пользователя {telegram_id}: {e}")
                return
            
            # Проверяем, включены ли уведомления
            if settings.get("dnd_enabled", False):
                logger.debug(f"Пользователь {telegram_id}: уведомления отключены (DND)")
                return
            
            # Получаем список времен уведомлений
            notify_times = settings.get("notify_times", [])
            if not notify_times:
                logger.debug(f"Пользователь {telegram_id}: нет времени уведомлений в настройках")
                return
            
            logger.debug(f"Пользователь {telegram_id}: время уведомлений={notify_times}, текущее время={current_time_str}")
            
            # Проверяем, нужно ли отправить уведомление сейчас
            if current_time_str not in notify_times:
                return
            
            # Проверяем, не отправляли ли мы уже уведомление в это время сегодня
            last_sent = self.last_sent_notifications.get(telegram_id, {})
            last_sent_date = last_sent.get(current_time_str)
            current_date = current_time.date()
            
            if last_sent_date == current_date:
                return  # Уже отправили сегодня в это время
            
            # Очищаем старые записи (старше 1 дня) для экономии памяти
            if last_sent_date and last_sent_date < current_date:
                self.last_sent_notifications[telegram_id] = {}
            
            # Получаем привычки пользователя
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
                logger.warning(f"Не удалось получить привычки для пользователя {telegram_id}: {e}")
                return
            
            # Отправляем уведомление со всеми привычками (выполненными и невыполненными)
            if not habits:
                logger.debug(f"Пользователь {telegram_id}: нет привычек")
                return  # Нет привычек вообще
            
            # Отправляем уведомление со всеми привычками
            await self._send_habits_notification(telegram_id, habits)
            
            # Сохраняем время отправки
            if telegram_id not in self.last_sent_notifications:
                self.last_sent_notifications[telegram_id] = {}
            self.last_sent_notifications[telegram_id][current_time_str] = current_time.date()
            
            logger.info(f"✅ Уведомление отправлено пользователю {telegram_id} в {current_time_str}, привычек: {len(habits)}")
            
        except Exception as e:
            logger.error(f"Ошибка при проверке уведомлений для пользователя {telegram_id}: {e}", exc_info=True)
    
    async def _send_habits_notification(self, telegram_id: int, habits: list):
        """Отправка уведомления о привычках пользователю"""
        try:
            message = self._format_habits_message(habits)
            keyboard = self._create_habits_keyboard(habits)
            
            sent_message = await self.bot.send_message(
                chat_id=telegram_id,
                text=message,
                reply_markup=keyboard
            )
            
            logger.info(f"Напоминание о привычках отправлено пользователю {telegram_id}, message_id={sent_message.message_id}, habits_count={len(habits)}")
            
        except TelegramForbiddenError:
            logger.warning(f"Пользователь {telegram_id} заблокировал бота")
        except TelegramBadRequest as e:
            logger.error(f"Ошибка Telegram API при отправке напоминания пользователю {telegram_id}: {e}")
        except Exception as e:
            logger.error(f"Ошибка при отправке напоминания пользователю {telegram_id}: {e}", exc_info=True)
    
    def _format_habits_message(self, habits: list) -> str:
        """Формирует текст сообщения с напоминанием о привычках"""
        text = "⏰ Напоминание о привычках:\n\n"
        
        # Разделяем на выполненные и невыполненные
        completed_habits = [h for h in habits if h.get("completed", False)]
        pending_habits = [h for h in habits if not h.get("completed", False)]
        
        # Сначала показываем невыполненные
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
        
        # Затем показываем выполненные
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
        """Создает клавиатуру с кнопками для быстрых действий"""
        keyboard = []
        
        # Кнопка для открытия списка привычек
        keyboard.append([
            InlineKeyboardButton(text="📋 Открыть список", callback_data="back_today")
        ])
        
        # Если есть невыполненные привычки, добавляем кнопку для отметки всех
        if habits:
            keyboard.append([
                InlineKeyboardButton(text="✅ Отметить все выполненными", callback_data="morning_complete_all")
            ])
        
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
