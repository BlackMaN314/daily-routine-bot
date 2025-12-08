"""
Вспомогательные функции для работы с пользователями и API
"""
from typing import Optional, Dict, Any
from aiogram import Bot
from aiogram.types import User
from config import BOT_TOKEN


async def get_user_photo_url(bot: Bot, user_id: int) -> Optional[str]:
    """
    Получить URL фотографии пользователя
    
    Args:
        bot: Объект бота
        user_id: ID пользователя в Telegram
        
    Returns:
        URL фотографии или None
    """
    try:
        photos = await bot.get_user_profile_photos(user_id=user_id, limit=1)
        if photos.total_count > 0 and photos.photos:
            photo = photos.photos[0]
            if photo:
                file_id = photo[-1].file_id
                file = await bot.get_file(file_id)
                photo_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file.file_path}"
                return photo_url
    except Exception:
        pass
    return None


async def get_user_params(user: User, bot: Bot) -> Dict[str, Any]:
    """
    Получить параметры пользователя для API запросов
    
    Args:
        user: Объект пользователя Telegram
        bot: Объект бота
        
    Returns:
        Словарь с параметрами пользователя
    """
    photo_url = await get_user_photo_url(bot, user.id)
    return {
        "telegram_id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "photo_url": photo_url
    }


def format_error_message(error: Exception) -> str:
    """
    Форматировать сообщение об ошибке для пользователя
    
    Args:
        error: Исключение
        
    Returns:
        Отформатированное сообщение об ошибке
    """
    error_str = str(error)
    if "Токен" in error_str or "токен" in error_str:
        return "❌ Проблема с авторизацией. Попробуй отправить /start"
    elif "сеть" in error_str.lower() or "network" in error_str.lower():
        return "📡 Проблема с подключением к серверу. Проверь интернет и попробуй еще раз."
    elif "404" in error_str or "не найдено" in error_str.lower():
        return "❌ Запрашиваемый ресурс не найден"
    else:
        return f"❌ Ошибка: {error_str}"

