"""
Скрипт для рассылки сообщений всем пользователям бота

Использование:
    python broadcast.py "Текст сообщения"

Или запустите скрипт и введите сообщение интерактивно:
    python broadcast.py
"""
import asyncio
import logging
import sys
import os
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from dotenv import load_dotenv
import aiosqlite

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_PATH = "data/tokens.db"


async def get_all_users():
    """Получить список всех пользователей из базы данных"""
    users = []
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT telegram_id, first_name, username FROM tokens"
            )
            rows = await cursor.fetchall()
            for row in rows:
                users.append({
                    "telegram_id": row[0],
                    "first_name": row[1] or "Пользователь",
                    "username": row[2] or None
                })
        logger.info(f"Найдено {len(users)} пользователей в базе данных")
        return users
    except Exception as e:
        logger.error(f"Ошибка при получении списка пользователей: {e}")
        return []


async def send_message_to_user(bot: Bot, telegram_id: int, message_text: str, user_info: dict):
    """Отправить сообщение пользователю"""
    try:
        await bot.send_message(
            chat_id=telegram_id,
            text=message_text,
            parse_mode="HTML"
        )
        logger.info(f"✅ Сообщение отправлено пользователю {telegram_id} ({user_info['first_name']})")
        return True
    except TelegramForbiddenError:
        logger.warning(f"❌ Пользователь {telegram_id} ({user_info['first_name']}) заблокировал бота")
        return False
    except TelegramBadRequest as e:
        logger.warning(f"❌ Ошибка при отправке пользователю {telegram_id}: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Неожиданная ошибка при отправке пользователю {telegram_id}: {e}")
        return False


async def broadcast_message(message_text: str, delay: float = 0.05):
    """
    Отправить сообщение всем пользователям
    
    Args:
        message_text: Текст сообщения для рассылки
        delay: Задержка между отправками (в секундах) для избежания rate limit
    """
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN не задан! Проверь .env файл")
        return
    
    bot = Bot(token=BOT_TOKEN)
    
    try:
        # Получаем список всех пользователей
        users = await get_all_users()
        
        if not users:
            logger.warning("Не найдено пользователей для рассылки")
            return
        
        logger.info(f"Начинаем рассылку сообщения {len(users)} пользователям...")
        logger.info(f"Текст сообщения: {message_text[:50]}...")
        
        # Статистика
        success_count = 0
        failed_count = 0
        blocked_count = 0
        
        # Отправляем сообщения
        for i, user in enumerate(users, 1):
            telegram_id = user["telegram_id"]
            logger.info(f"[{i}/{len(users)}] Отправка пользователю {telegram_id} ({user['first_name']})...")
            
            result = await send_message_to_user(bot, telegram_id, message_text, user)
            
            if result:
                success_count += 1
            else:
                failed_count += 1
                # Проверяем, заблокирован ли бот
                try:
                    await bot.get_chat(telegram_id)
                except TelegramForbiddenError:
                    blocked_count += 1
            
            # Задержка между отправками для избежания rate limit
            if i < len(users):
                await asyncio.sleep(delay)
        
        # Итоговая статистика
        logger.info("\n" + "="*50)
        logger.info("📊 ИТОГИ РАССЫЛКИ:")
        logger.info(f"✅ Успешно отправлено: {success_count}")
        logger.info(f"❌ Ошибок: {failed_count}")
        logger.info(f"🚫 Заблокировали бота: {blocked_count}")
        logger.info(f"📈 Всего пользователей: {len(users)}")
        logger.info("="*50)
        
    except Exception as e:
        logger.error(f"Критическая ошибка при рассылке: {e}", exc_info=True)
    finally:
        await bot.session.close()


async def main():
    """Главная функция"""
    # Получаем текст сообщения из аргументов командной строки или интерактивно
    if len(sys.argv) > 1:
        # Сообщение передано как аргумент
        message_text = " ".join(sys.argv[1:])
    else:
        # Запрашиваем сообщение интерактивно
        print("\n" + "="*50)
        print("📢 РАССЫЛКА СООБЩЕНИЙ ВСЕМ ПОЛЬЗОВАТЕЛЯМ")
        print("="*50)
        print("\nВведите текст сообщения для рассылки:")
        print("(Для многострочного текста используйте \\n для переноса строки)")
        print("(Или нажмите Enter для отмены)\n")
        
        message_text = input("Сообщение: ").strip()
        
        if not message_text:
            print("❌ Сообщение пустое. Рассылка отменена.")
            return
        
        # Заменяем \n на реальные переносы строк
        message_text = message_text.replace("\\n", "\n")
        
        # Подтверждение
        print(f"\n📝 Текст сообщения:\n{message_text}\n")
        confirm = input("Отправить это сообщение всем пользователям? (yes/no): ").strip().lower()
        
        if confirm not in ["yes", "y", "да", "д"]:
            print("❌ Рассылка отменена.")
            return
    
    # Запускаем рассылку
    await broadcast_message(message_text)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n⚠️  Рассылка прервана пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        sys.exit(1)

