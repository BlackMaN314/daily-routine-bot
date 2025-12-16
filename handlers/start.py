from aiogram import Router, types, Bot
from aiogram.filters import Command
from keyboards.main_menu import main_menu
from services.api import api
from config import WEB_APP_URL
from utils.helpers import get_user_photo_url

router = Router()

@router.message(Command("start"))
async def cmd_start(message: types.Message, bot: Bot):
    if not message.from_user:
        return
    
    user_id = message.from_user.id
    
    try:
        photo_url = await get_user_photo_url(bot, user_id)
        user_data = await api.register_telegram_user(
            telegram_id=user_id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            photo_url=photo_url
        )
        
        # Сохраняем токены после успешной авторизации/регистрации
        from services.token_storage import token_storage
        import logging
        logger = logging.getLogger(__name__)
        
        tokens = user_data.get("tokens", {})
        user = user_data.get("user", {})
        access_token = tokens.get("access_token")
        refresh_token = tokens.get("refresh_token")
        backend_user_id = user.get("id")
        
        if access_token and refresh_token:
            await token_storage.save_tokens(
                telegram_id=user_id,
                access_token=access_token,
                refresh_token=refresh_token,
                user_id=backend_user_id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
                photo_url=photo_url
            )
        else:
            logger.error(f"Токены не получены при авторизации для telegram_id={user_id}")
        
        await message.answer(
            "✅ <b>Авторизация успешна!</b>\n\n"
            "👋 <b>Привет! Я DailyRoutine Bot!</b>\n\n"
            "Я помогу тебе отслеживать ежедневные привычки и достигать целей! 🎯\n\n"
            "✨ <b>Возможности:</b>\n"
            "🔔 Получай напоминания\n"
            "📊 Отслеживай прогресс\n"
            "🔥 Поддерживай серии\n\n"
            "🚀 <b>Готов начать?</b>",
            reply_markup=types.ReplyKeyboardMarkup(
                keyboard=[
                    [types.KeyboardButton(text="✅ Да, начать!")],
                    [types.KeyboardButton(text="📖 Узнать больше")]
                ],
                resize_keyboard=True
            ),
            parse_mode="HTML"
        )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Ошибка при авторизации пользователя telegram_id={user_id}: {e}", exc_info=True)
        
        try:
            reg_data = await api.get("/telegram/registration-link", params={"telegram_id": user_id})
            registration_url = reg_data.get("url", WEB_APP_URL)
            
            await message.answer(
                "👋 Привет! Я DailyRoutine Bot!\n\n"
                "Не удалось автоматически авторизоваться.\n\n"
                "Попробуй зарегистрироваться через веб-версию:\n\n"
                "После регистрации ты сможешь:\n"
                "🔔 Получать напоминания\n"
                "📊 Отслеживать прогресс\n"
                "🔥 Поддерживать серии\n\n"
                "Нажми на кнопку ниже, чтобы перейти к регистрации:",
                reply_markup=types.InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            types.InlineKeyboardButton(
                                text="📝 Зарегистрироваться",
                                url=registration_url
                            )
                        ],
                        [
                            types.InlineKeyboardButton(
                                text="🔄 Попробовать снова",
                                callback_data="check_registration"
                            )
                        ]
                    ]
                )
            )
        except Exception:
            await message.answer(
                f"❌ Не удалось авторизоваться.\n"
                f"Попробуй позже или обратись в поддержку.\n\n"
                f"Ошибка: {str(e)}"
            )

@router.message(lambda m: m.text == "✅ Да, начать!")
async def start_onboarding(message: types.Message):
    await message.answer(
        "Отлично! Давай начнем! 🚀\n\n"
        "Используй меню ниже для навигации:",
        reply_markup=main_menu()
    )

@router.message(lambda m: m.text == "📖 Узнать больше")
async def show_info(message: types.Message):
    await message.answer(
        "📖 <b>Как это работает:</b>\n\n"
        "1️⃣ Создай привычку в боте или веб-версии\n"
        "2️⃣ Бот будет напоминать тебе каждый день\n"
        "3️⃣ Отмечай выполнение и смотри прогресс\n"
        "4️⃣ Поддерживай серии и получай мотивацию!\n\n"
        "🚀 <b>Готов начать?</b>\n\n"
        "Используй меню ниже для навигации:\n"
        "📅 <b>Привычки</b> - создай и управляй привычками\n"
        "⚙️ <b>Настройки</b> - настрой уведомления\n"
        "👤 <b>Личный кабинет</b> - открой веб-версию",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )

@router.callback_query(lambda c: c.data == "check_registration")
async def check_registration(call: types.CallbackQuery, bot: Bot):
    if not call.from_user:
        return await call.answer("❌ Ошибка", show_alert=True)
    
    user_id = call.from_user.id
    await call.answer()
    
    try:
        photo_url = await get_user_photo_url(bot, user_id)
        
        user_data = await api.register_telegram_user(
            telegram_id=user_id,
            username=call.from_user.username,
            first_name=call.from_user.first_name,
            last_name=call.from_user.last_name,
            photo_url=photo_url
        )
        
        # Сохраняем токены после успешной авторизации/регистрации
        from services.token_storage import token_storage
        import logging
        logger = logging.getLogger(__name__)
        
        tokens = user_data.get("tokens", {})
        user = user_data.get("user", {})
        access_token = tokens.get("access_token")
        refresh_token = tokens.get("refresh_token")
        backend_user_id = user.get("id")
        
        if access_token and refresh_token:
            await token_storage.save_tokens(
                telegram_id=user_id,
                access_token=access_token,
                refresh_token=refresh_token,
                user_id=backend_user_id,
                username=call.from_user.username,
                first_name=call.from_user.first_name,
                last_name=call.from_user.last_name,
                photo_url=photo_url
            )
        else:
            logger.error(f"Токены не получены при авторизации для telegram_id={user_id}")
        
        if call.message:
            await call.message.edit_text(
                "✅ Авторизация успешна!\n\n"
                "👋 Привет! Я DailyRoutine Bot!\n\n"
                "Я помогу тебе отслеживать ежедневные привычки и достигать целей!\n\n"
                "Готов начать?",
                reply_markup=types.ReplyKeyboardMarkup(
                    keyboard=[
                        [types.KeyboardButton(text="✅ Да, начать!")],
                        [types.KeyboardButton(text="📖 Узнать больше")]
                    ],
                    resize_keyboard=True
                )
            )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Ошибка при авторизации пользователя telegram_id={user_id}: {e}", exc_info=True)
        
        try:
            reg_data = await api.get("/telegram/registration-link", params={"telegram_id": user_id})
            registration_url = reg_data.get("url", WEB_APP_URL)
            
            if call.message:
                await call.message.edit_text(
                    "❌ Автоматическая авторизация не удалась.\n\n"
                    "Попробуй зарегистрироваться через веб-версию:\n\n"
                    "Нажми на кнопку ниже, чтобы перейти к регистрации:",
                    reply_markup=types.InlineKeyboardMarkup(
                        inline_keyboard=[
                            [
                                types.InlineKeyboardButton(
                                    text="📝 Зарегистрироваться",
                                    url=registration_url
                                )
                            ],
                            [
                                types.InlineKeyboardButton(
                                    text="🔄 Попробовать снова",
                                    callback_data="check_registration"
                                )
                            ]
                        ]
                    )
                )
        except Exception:
            if call.message:
                await call.message.edit_text(
                    f"❌ Не удалось авторизоваться.\n"
                    f"Попробуй позже или обратись в поддержку.\n\n"
                    f"Ошибка: {str(e)}"
                )

@router.message(lambda m: m.text == "🌐 Открыть веб-версию")
async def open_web(message: types.Message):
    if not message.from_user:
        return
    
    try:
        data = await api.get(f"/telegram/auth-link", params={"telegram_id": message.from_user.id})
        web_url = data.get("url", WEB_APP_URL)
        
        await message.answer(
            "🌐 Открой веб-версию для управления привычками:",
            reply_markup=types.InlineKeyboardMarkup(
                inline_keyboard=[[
                    types.InlineKeyboardButton(text="🌐 Открыть веб-версию", url=web_url)
                ]]
            )
        )
    except Exception as e:
        await message.answer(
            f"❌ Не удалось получить ссылку на веб-версию.\n"
            f"Попробуй позже или обратись в поддержку.",
            reply_markup=main_menu()
        )
