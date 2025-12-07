from aiogram import Router, types, Bot
from aiogram.filters import Command
from typing import Optional
from keyboards.main_menu import main_menu
from services.api import api
from config import WEB_APP_URL, BOT_TOKEN

router = Router()


async def get_user_photo_url(bot: Bot, user_id: int) -> Optional[str]:
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

@router.message(Command("start"))
async def cmd_start(message: types.Message, bot: Bot):
    if not message.from_user:
        return
    
    user_id = message.from_user.id
    
    user_exists = False
    try:
        check_data = await api.get("/telegram/users/check", params={"telegram_id": user_id})
        user_exists = check_data.get("exists", False)
    except Exception:
        user_exists = False
    
    if not user_exists:
        try:
            photo_url = await get_user_photo_url(bot, user_id)
            user_data = await api.register_telegram_user(
                telegram_id=user_id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
                photo_url=photo_url
            )
            await message.answer(
                "✅ Регистрация успешна!\n\n"
                "👋 Привет! Я DailyRoutine Bot!\n\n"
                "Я помогу тебе отслеживать ежедневные привычки и достигать целей!\n\n"
                "🔔 Получай напоминания\n"
                "📊 Отслеживай прогресс\n"
                "🔥 Поддерживай серии\n\n"
                "Готов начать?",
                reply_markup=types.ReplyKeyboardMarkup(
                    keyboard=[
                        [types.KeyboardButton(text="✅ Да, начать!")],
                        [types.KeyboardButton(text="📖 Узнать больше")]
                    ],
                    resize_keyboard=True
                )
            )
            return
        except Exception as e:
            try:
                reg_data = await api.get("/telegram/registration-link", params={"telegram_id": user_id})
                registration_url = reg_data.get("url", WEB_APP_URL)
                
                await message.answer(
                    "👋 Привет! Я DailyRoutine Bot!\n\n"
                    "Для начала работы тебе нужно зарегистрироваться.\n\n"
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
                                    text="🔄 Проверить регистрацию",
                                    callback_data="check_registration"
                                )
                            ]
                        ]
                    )
                )
            except Exception:
                await message.answer(
                    f"❌ Не удалось зарегистрироваться.\n"
                    f"Попробуй позже или обратись в поддержку.\n\n"
                    f"Ошибка: {str(e)}"
                )
        return
    
    await message.answer(
        "👋 Привет! Я DailyRoutine Bot!\n\n"
        "Я помогу тебе отслеживать ежедневные привычки и достигать целей!\n\n"
        "🔔 Получай напоминания\n"
        "📊 Отслеживай прогресс\n"
        "🔥 Поддерживай серии\n\n"
        "Готов начать?",
        reply_markup=types.ReplyKeyboardMarkup(
            keyboard=[
                [types.KeyboardButton(text="✅ Да, начать!")],
                [types.KeyboardButton(text="📖 Узнать больше")]
            ],
            resize_keyboard=True
        )
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
        "📖 Как это работает:\n\n"
        "1️⃣ Создай привычку в веб-версии\n"
        "2️⃣ Бот будет напоминать тебе каждый день\n"
        "3️⃣ Отмечай выполнение и смотри статистику\n"
        "4️⃣ Поддерживай серии и получай мотивацию!\n\n"
        "Готов начать?",
        reply_markup=types.ReplyKeyboardMarkup(
            keyboard=[
                [types.KeyboardButton(text="🌐 Открыть веб-версию")],
                [types.KeyboardButton(text="🏠 Главное меню")]
            ],
            resize_keyboard=True
        )
    )

@router.callback_query(lambda c: c.data == "check_registration")
async def check_registration(call: types.CallbackQuery, bot: Bot):
    if not call.from_user:
        return await call.answer("❌ Ошибка", show_alert=True)
    
    user_id = call.from_user.id
    user_exists = False
    try:
        check_data = await api.get("/telegram/users/check", params={"telegram_id": user_id})
        user_exists = check_data.get("exists", False)
    except Exception:
        try:
            await api.get("/telegram/settings", params={"telegram_id": user_id})
            user_exists = True
        except Exception:
            user_exists = False
    
    await call.answer()
    
    if user_exists:
        if call.message:
            await call.message.answer(
                "✅ Отлично! Ты зарегистрирован!\n\n"
                "👋 Привет! Я DailyRoutine Bot!\n\n"
                "Я помогу тебе отслеживать ежедневные привычки и достигать целей!\n\n"
                "🔔 Получай напоминания\n"
                "📊 Отслеживай прогресс\n"
                "🔥 Поддерживай серии\n\n"
                "Готов начать?",
                reply_markup=types.ReplyKeyboardMarkup(
                    keyboard=[
                        [types.KeyboardButton(text="✅ Да, начать!")],
                        [types.KeyboardButton(text="📖 Узнать больше")]
                    ],
                    resize_keyboard=True
                )
            )
    else:
        try:
            photo_url = await get_user_photo_url(bot, user_id)
            
            user_data = await api.register_telegram_user(
                telegram_id=user_id,
                username=call.from_user.username,
                first_name=call.from_user.first_name,
                last_name=call.from_user.last_name,
                photo_url=photo_url
            )
            if call.message:
                await call.message.edit_text(
                    "✅ Регистрация успешна!\n\n"
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
            try:
                reg_data = await api.get("/telegram/registration-link", params={"telegram_id": user_id})
                registration_url = reg_data.get("url", WEB_APP_URL)
                
                if call.message:
                    await call.message.edit_text(
                        "❌ Автоматическая регистрация не удалась.\n\n"
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
                                        text="🔄 Проверить снова",
                                        callback_data="check_registration"
                                    )
                                ]
                            ]
                        )
                    )
            except Exception:
                if call.message:
                    await call.message.edit_text(
                        f"❌ Не удалось зарегистрироваться.\n"
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
