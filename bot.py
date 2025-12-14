import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config import BOT_TOKEN, BACKEND_URL, NOTIFICATION_SERVER_HOST, NOTIFICATION_SERVER_PORT
from services.api import api
from services.token_storage import TokenStorage
from services.notification_server import NotificationServer
from services.notification_scheduler import NotificationScheduler

from handlers import start, main_menu, habits_today, habit_actions, habit_manage, settings, profile, notifications

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)


async def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN не задан! Проверь .env файл")

    if not BACKEND_URL:
        logger.warning("BACKEND_URL не задан! Будет использовано значение по умолчанию: http://localhost:8000")
    else:
        logger.info(f"Запуск бота. Backend URL: {BACKEND_URL}")

    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    from middleware.throttling import ThrottlingMiddleware
    dp.message.middleware(ThrottlingMiddleware(rate_limit=1.0))
    dp.callback_query.middleware(ThrottlingMiddleware(rate_limit=0.5))
    logger.info("Защита от спама активирована")
    
    bot_info = await bot.get_me()
    from services import token_storage as token_storage_module
    token_storage_module.token_storage = TokenStorage(bot_id=bot_info.id)
    await token_storage_module.token_storage._init_db()
    logger.info("База данных токенов инициализирована")
    
    logger.info("Проверка подключения к бэкенду...")
    if await api.check_connection():
        logger.info("✅ Подключение к бэкенду успешно")
    else:
        logger.warning(f"⚠️  Не удалось подключиться к бэкенду на {BACKEND_URL}")
        logger.warning("Бот будет работать, но некоторые функции могут быть недоступны")
    dp.include_router(start.router)
    dp.include_router(main_menu.router)
    dp.include_router(habits_today.router)
    dp.include_router(habit_actions.router)
    dp.include_router(habit_manage.router)
    dp.include_router(settings.router)
    dp.include_router(profile.router)
    dp.include_router(notifications.router)

    notification_server = None
    notification_scheduler = None
    
    try:
        notification_server = NotificationServer(
            bot=bot,
            host=NOTIFICATION_SERVER_HOST,
            port=NOTIFICATION_SERVER_PORT
        )
        await notification_server.start()
    except Exception as e:
        logger.error(f"Ошибка при запуске HTTP сервера уведомлений: {e}", exc_info=True)
        logger.warning("Бот будет работать без HTTP сервера уведомлений")
    
    try:
        notification_scheduler = NotificationScheduler(bot=bot, check_interval=10)
        await notification_scheduler.start()
        logger.info("Планировщик уведомлений запущен (интервал проверки: 10 секунд)")
    except Exception as e:
        logger.error(f"Ошибка при запуске планировщика уведомлений: {e}", exc_info=True)
        logger.warning("Бот будет работать без планировщика уведомлений")

    try:
        logger.info("Бот запущен и готов к работе")
        await dp.start_polling(bot, handle_as_tasks=True)
    except Exception as e:
        logger.error(f"Ошибка при работе бота: {e}", exc_info=True)
    finally:
        logger.info("Закрываем соединения...")
        if notification_scheduler:
            try:
                await notification_scheduler.stop()
            except Exception as e:
                logger.error(f"Ошибка при остановке планировщика: {e}")
        if notification_server:
            try:
                await notification_server.stop()
            except Exception as e:
                logger.error(f"Ошибка при остановке HTTP сервера: {e}")
        await api.close()
        await bot.session.close()
        logger.info("Бот остановлен")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Получен сигнал прерывания")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        sys.exit(1)
