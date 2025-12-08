from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.exceptions import TelegramBadRequest
from services.api import api
from utils.helpers import get_user_photo_url

router = Router()

def get_habits_keyboard(habits: list):
    keyboard = []
    for habit in habits:
        habit_id = habit.get("id")
        name = habit.get("name", "Неизвестно")
        completed = habit.get("completed", False)
        status_emoji = "✅" if completed else "❌"
        keyboard.append([InlineKeyboardButton(
            text=f"{status_emoji} {name}",
            callback_data=f"habit_select:{habit_id}"
        )])
    keyboard.append([InlineKeyboardButton(text="➕ Создать привычку", callback_data="habit_create")])
    keyboard.append([InlineKeyboardButton(text="🔄 Обновить список", callback_data="refresh_habits")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

@router.message(lambda m: m.text == "📅 Привычки")
async def habits_today(message: types.Message):
    if not message.from_user:
        return await message.answer("❌ Не удалось определить пользователя")

    user_id = message.from_user.id

    try:
        photo_url = await get_user_photo_url(message.bot, user_id)
        data = await api.get("/habits/today", params={
            "telegram_id": user_id,
            "username": message.from_user.username,
            "first_name": message.from_user.first_name,
            "last_name": message.from_user.last_name,
            "photo_url": photo_url
        })
    except Exception as e:
        error_msg = str(e)
        if "Не удалось подключиться к серверу" in error_msg:
            text = f"📡 Не удалось подключиться к серверу\n\n{error_msg}\n\nПроверь:\n• Запущен ли бэкенд\n• Правильность BACKEND_URL в настройках"
        elif "Токен" in error_msg or "токен" in error_msg:
            text = "❌ Проблема с авторизацией\n\nПопробуй отправить /start для повторной регистрации"
        else:
            text = f"❌ Ошибка: {error_msg}\n\nПопробуй еще раз или обратись в поддержку."
        
        return await message.answer(
            text,
            reply_markup=types.ReplyKeyboardMarkup(
                keyboard=[
                    [types.KeyboardButton(text="🔄 Повторить")]
                ],
                resize_keyboard=True
            )
        )

    habits = data.get("habits", [])
    if not habits:
        await message.answer(
            "📝 <b>У тебя пока нет привычек</b>\n\n"
            "Создай первую привычку прямо здесь! 🚀",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="➕ Создать привычку", callback_data="habit_create")],
                    [InlineKeyboardButton(text="👤 Личный кабинет", callback_data="profile")]
                ]
            ),
            parse_mode="HTML"
        )
        return

    await message.answer(
        "📋 <b>Твои привычки:</b>",
        reply_markup=get_habits_keyboard(habits),
        parse_mode="HTML"
    )

@router.message(lambda m: m.text == "🔄 Обновить список")
async def refresh_habits(message: types.Message):
    await habits_today(message)

@router.message(lambda m: m.text == "📋 Выбрать привычку")
async def select_habit(message: types.Message):
    await habits_today(message)

@router.callback_query(lambda c: c.data == "refresh_habits")
async def refresh_habits_callback(call: types.CallbackQuery):
    if not call.from_user or not call.message:
        return await call.answer("❌ Ошибка", show_alert=True)
    
    await call.answer("Обновляю список...")
    
    user_id = call.from_user.id
    
    try:
        photo_url = await get_user_photo_url(call.bot, user_id)
        data = await api.get("/habits/today", params={
            "telegram_id": user_id,
            "username": call.from_user.username,
            "first_name": call.from_user.first_name,
            "last_name": call.from_user.last_name,
            "photo_url": photo_url
        })
        habits = data.get("habits", [])
        
        if not habits:
            await call.message.edit_text(
                "📝 <b>У тебя пока нет привычек</b>\n\n"
                "Создай первую привычку прямо здесь! 🚀",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="➕ Создать привычку", callback_data="habit_create")]
                    ]
                ),
                parse_mode="HTML"
            )
            return
        
        try:
            await call.message.edit_text(
                "📋 <b>Твои привычки:</b>",
                reply_markup=get_habits_keyboard(habits),
                parse_mode="HTML"
            )
        except TelegramBadRequest as e:
            if "message is not modified" in str(e).lower():
                await call.answer("Список уже актуален ✅")
            else:
                raise
    except Exception as e:
        try:
            await call.message.edit_text(
                f"❌ Ошибка при загрузке привычек: {e}",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="refresh_habits")]
                    ]
                )
            )
        except TelegramBadRequest as e2:
            # Если не удалось отредактировать, просто отвечаем
            if "message is not modified" in str(e2).lower():
                await call.answer("Список уже актуален ✅")
            else:
                await call.answer(f"❌ Ошибка: {e}", show_alert=True)

@router.callback_query(lambda c: c.data and c.data.startswith("habit_select:"))
async def show_habit_details(call: types.CallbackQuery, state: FSMContext = None):
    if not call.data or not call.from_user:
        return await call.answer("❌ Ошибка", show_alert=True)
    
    try:
        if state:
            await state.clear()
    except Exception:
        pass
    
    habit_id = call.data.split(":")[1]
    user_id = call.from_user.id

    try:
        photo_url = await get_user_photo_url(call.bot, user_id)
        data = await api.get(f"/habits/{habit_id}", params={
            "telegram_id": user_id,
            "username": call.from_user.username,
            "first_name": call.from_user.first_name,
            "last_name": call.from_user.last_name,
            "photo_url": photo_url
        })
        habit = data.get("habit", {})
        
        name = habit.get("name", "Неизвестно")
        progress = habit.get("progress", 0)
        goal = habit.get("goal", 0)
        unit = habit.get("unit", "")
        streak = habit.get("streak", 0)
        emoji = habit.get("emoji", "📌")
        
        completed = habit.get("completed", False)
        
        status_icon = "✅" if completed else "⏳"
        text = f"{status_icon} <b>{name}</b>\n"
        
        habit_type = habit.get("type", "boolean")
        if habit_type == "quantity" and unit:
            text += f"📊 Цель: {goal} {unit}\n"
            text += f"📈 Прогресс: {progress} / {goal} {unit}\n"
        elif habit_type == "quantity":
            text += f"📊 Цель: {goal}\n"
            text += f"📈 Прогресс: {progress} / {goal}\n"
        
        if streak > 0:
            text += f"🔥 Серия: {streak} дней подряд"
        
        keyboard_buttons = []
        if completed:
            keyboard_buttons.append([InlineKeyboardButton(text="❌ Отменить выполнение", callback_data=f"habit_undo:{habit_id}")])
        else:
            keyboard_buttons.append([InlineKeyboardButton(text="✅ Выполнить", callback_data=f"habit_complete:{habit_id}")])
        
        keyboard_buttons.extend([
            [InlineKeyboardButton(text="🗑️ Удалить привычку", callback_data=f"habit_delete:{habit_id}")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_today")]
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        try:
            await call.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        except TelegramBadRequest as e:
            if "message is not modified" in str(e).lower():
                await call.answer("Информация уже актуальна ✅")
            else:
                raise
        await call.answer()
    except Exception as e:
        await call.answer(f"❌ Ошибка: {e}", show_alert=True)

@router.callback_query(lambda c: c.data == "back_today")
async def back_to_today(call: types.CallbackQuery, state: FSMContext = None):
    if not call.from_user or not call.message:
        return await call.answer("❌ Ошибка", show_alert=True)
    
    try:
        if state:
            await state.clear()
    except Exception:
        pass
    
    await call.answer()
    
    user_id = call.from_user.id
    
    try:
        photo_url = await get_user_photo_url(call.bot, user_id)
        data = await api.get("/habits/today", params={
            "telegram_id": user_id,
            "username": call.from_user.username,
            "first_name": call.from_user.first_name,
            "last_name": call.from_user.last_name,
            "photo_url": photo_url
        })
        habits = data.get("habits", [])
        
        if not habits:
            await call.message.edit_text(
                "📝 <b>У тебя пока нет привычек</b>\n\n"
                "Создай первую привычку прямо здесь! 🚀",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="➕ Создать привычку", callback_data="habit_create")]
                    ]
                ),
                parse_mode="HTML"
            )
            return
        
        try:
            await call.message.edit_text(
                "📋 <b>Твои привычки:</b>",
                reply_markup=get_habits_keyboard(habits),
                parse_mode="HTML"
            )
        except TelegramBadRequest as e:
            if "message is not modified" in str(e).lower():
                await call.answer("Список уже актуален ✅")
            else:
                raise
    except Exception as e:
        try:
            await call.message.edit_text(
                f"❌ Ошибка при загрузке привычек: {e}",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="back_today")]
                    ]
                )
            )
        except TelegramBadRequest:
            await call.answer(f"❌ Ошибка: {e}", show_alert=True)
