from aiogram import Router, types, Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.exceptions import TelegramBadRequest
from services.api import api
from keyboards.main_menu import main_menu
from handlers.start import get_user_photo_url

router = Router()

def get_habits_keyboard(habits: list):
    keyboard = []
    for habit in habits:
        habit_id = habit.get("id")
        name = habit.get("name", "Неизвестно")
        emoji = habit.get("emoji", "📌")
        keyboard.append([InlineKeyboardButton(
            text=f"{emoji} {name}",
            callback_data=f"habit_select:{habit_id}"
        )])
    keyboard.append([InlineKeyboardButton(text="➕ Создать привычку", callback_data="habit_create")])
    keyboard.append([InlineKeyboardButton(text="🔄 Обновить список", callback_data="refresh_habits")])
    keyboard.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

@router.message(lambda m: m.text == "📅 Привычки на сегодня")
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
        return await message.answer(
            "📡 Нет соединения с сервером\n\n"
            "Проверь подключение к интернету и попробуй еще раз.",
            reply_markup=types.ReplyKeyboardMarkup(
                keyboard=[
                    [types.KeyboardButton(text="🔄 Повторить")],
                    [types.KeyboardButton(text="🔙 Главное меню")]
                ],
                resize_keyboard=True
            )
        )

    habits = data.get("habits", [])
    if not habits:
        await message.answer(
            "У тебя пока нет привычек 😔\n\n"
            "Создай первую привычку прямо здесь!",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="➕ Создать привычку", callback_data="habit_create")],
                    [InlineKeyboardButton(text="👤 Личный кабинет", callback_data="profile")],
                    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
                ]
            )
        )
        return

    text = "Твои привычки на сегодня:\n\n"
    for h in habits:
        icon = "✅" if h.get("completed") else "❌"
        name = h.get("name", "Неизвестно")
        progress = h.get("progress", 0)
        goal = h.get("goal", 0)
        unit = h.get("unit", "")
        if unit:
            text += f"{icon} {name} — {progress} / {goal} {unit}\n"
        else:
            text += f"{icon} {name} — {progress} / {goal}\n"

    await message.answer(
        text,
        reply_markup=types.ReplyKeyboardMarkup(
            keyboard=[
                [types.KeyboardButton(text="🔄 Обновить список")],
                [types.KeyboardButton(text="📋 Выбрать привычку")],
                [types.KeyboardButton(text="🏠 Главное меню")]
            ],
            resize_keyboard=True
        )
    )

@router.message(lambda m: m.text == "🔄 Обновить список")
async def refresh_habits(message: types.Message):
    await habits_today(message)

@router.message(lambda m: m.text == "📋 Выбрать привычку")
async def select_habit(message: types.Message):
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
        habits = data.get("habits", [])
        
        if not habits:
            await message.answer(
                "У тебя пока нет привычек 😔\n\n"
                "Создай первую привычку прямо здесь!",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="➕ Создать привычку", callback_data="habit_create")],
                        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
                    ]
                )
            )
            return

        await message.answer(
            "Выбери привычку:",
            reply_markup=get_habits_keyboard(habits)
        )
    except Exception as e:
        await message.answer(
            f"❌ Ошибка при загрузке привычек: {e}",
            reply_markup=main_menu()
        )

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
                "У тебя пока нет привычек 😔\n\n"
                "Создай первую привычку прямо здесь!",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="➕ Создать привычку", callback_data="habit_create")],
                        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
                    ]
                )
            )
            return
        
        try:
            await call.message.edit_text(
                "Выбери привычку:",
                reply_markup=get_habits_keyboard(habits)
            )
        except TelegramBadRequest as e:
            # Если сообщение не изменилось, просто отвечаем на callback
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
                        [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="refresh_habits")],
                        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
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
async def show_habit_details(call: types.CallbackQuery):
    if not call.data or not call.from_user:
        return await call.answer("❌ Ошибка", show_alert=True)
    
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
        
        text = f"{emoji} {name}"
        if unit:
            text += f" {goal} {unit}"
        text += f"\nПрогресс: {progress} / {goal}"
        if unit:
            text += f" {unit}"
        text += f"\nСерия: {streak} дней 🔥"
        
        keyboard_buttons = []
        if completed:
            keyboard_buttons.append([InlineKeyboardButton(text="❌ Отменить выполнение", callback_data=f"habit_undo:{habit_id}")])
        else:
            keyboard_buttons.append([InlineKeyboardButton(text="✅ Выполнить", callback_data=f"habit_complete:{habit_id}")])
        
        keyboard_buttons.extend([
            [InlineKeyboardButton(text="📈 Статистика", callback_data=f"habit_stats:{habit_id}")],
            [InlineKeyboardButton(text="🗑️ Удалить привычку", callback_data=f"habit_delete:{habit_id}")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_today")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        try:
            await call.message.edit_text(text, reply_markup=keyboard)
        except TelegramBadRequest as e:
            if "message is not modified" in str(e).lower():
                await call.answer("Информация уже актуальна ✅")
            else:
                raise
        await call.answer()
    except Exception as e:
        await call.answer(f"❌ Ошибка: {e}", show_alert=True)

@router.callback_query(lambda c: c.data == "back_today")
async def back_to_today(call: types.CallbackQuery):
    if not call.from_user or not call.message:
        return await call.answer("❌ Ошибка", show_alert=True)
    
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
                "У тебя пока нет привычек 😔\n\n"
                "Создай первую привычку прямо здесь!",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="➕ Создать привычку", callback_data="habit_create")],
                        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
                    ]
                )
            )
            return
        
        try:
            await call.message.edit_text(
                "Выбери привычку:",
                reply_markup=get_habits_keyboard(habits)
            )
        except TelegramBadRequest as e:
            # Если сообщение не изменилось, просто отвечаем на callback
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
                        [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="back_today")],
                        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
                    ]
                )
            )
        except TelegramBadRequest:
            # Если не удалось отредактировать, просто отвечаем
            await call.answer(f"❌ Ошибка: {e}", show_alert=True)
