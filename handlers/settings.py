from aiogram import Router, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from services.api import api
from keyboards.main_menu import main_menu
from handlers.start import get_user_photo_url
from datetime import datetime
import re

router = Router()


class SettingsStates(StatesGroup):
    waiting_for_notification_time = State()
    waiting_for_dnd_start = State()
    waiting_for_dnd_end = State()


def get_settings_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔔 Напоминания", callback_data="settings_reminders")],
            [InlineKeyboardButton(text="🌙 Не беспокоить", callback_data="settings_dnd")],
            [InlineKeyboardButton(text="🕓 Время уведомлений", callback_data="settings_time")],
            [InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")]
        ]
    )


def get_reminders_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Выключить все", callback_data="reminders_disable_all")],
            [InlineKeyboardButton(text="🕓 Изменить время", callback_data="settings_time")],
            [InlineKeyboardButton(text="🔔 Настройки по привычкам", callback_data="reminders_habits")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="settings_main")]
        ]
    )


def get_time_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🕓 07:00", callback_data="time_set:07:00")],
            [InlineKeyboardButton(text="🕓 08:00", callback_data="time_set:08:00")],
            [InlineKeyboardButton(text="🕔 09:00", callback_data="time_set:09:00")],
            [InlineKeyboardButton(text="🕔 10:00", callback_data="time_set:10:00")],
            [InlineKeyboardButton(text="⏰ Кастомное", callback_data="time_custom")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="settings_main")]
        ]
    )


def get_dnd_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🌙 Включить", callback_data="dnd_enable")],
            [InlineKeyboardButton(text="❌ Выключить", callback_data="dnd_disable")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="settings_main")]
        ]
    )


@router.message(lambda m: m.text == "⚙️ Настройки")
async def show_settings(message: types.Message):
    if not message.from_user:
        return await message.answer("❌ Не удалось определить пользователя")

    user_id = message.from_user.id

    try:
        photo_url = await get_user_photo_url(message.bot, user_id)
        data = await api.get("/telegram/settings", params={
            "telegram_id": user_id,
            "username": message.from_user.username,
            "first_name": message.from_user.first_name,
            "last_name": message.from_user.last_name,
            "photo_url": photo_url
        })
        settings = data.get("settings", {})
        
        reminders_enabled = settings.get("reminders_enabled", True)
        morning_time = settings.get("morning_time", "08:00")
        dnd_enabled = settings.get("dnd_enabled", False)
        
        text = "⚙️ Настройки:\n"
        text += "Выбери, что хочешь изменить 👇"
        
        await message.answer(text, reply_markup=get_settings_keyboard())
    except Exception as e:
        await message.answer(
            f"❌ Ошибка при загрузке настроек: {e}",
            reply_markup=main_menu()
        )


@router.callback_query(lambda c: c.data == "settings_main")
async def settings_main(call: types.CallbackQuery):
    """Возврат в главное меню настроек"""
    await call.answer()
    if call.message:
        await call.message.edit_text(
            "⚙️ Настройки:\nВыбери, что хочешь изменить 👇",
            reply_markup=get_settings_keyboard()
        )


@router.callback_query(lambda c: c.data == "settings_reminders")
async def show_reminders_settings(call: types.CallbackQuery):
    if not call.from_user:
        return await call.answer("❌ Ошибка", show_alert=True)
    
    user_id = call.from_user.id

    try:
        photo_url = await get_user_photo_url(call.bot, user_id)
        data = await api.get("/telegram/settings", params={
            "telegram_id": user_id,
            "username": call.from_user.username,
            "first_name": call.from_user.first_name,
            "last_name": call.from_user.last_name,
            "photo_url": photo_url
        })
        settings = data.get("settings", {})
        
        reminders_enabled = settings.get("reminders_enabled", True)
        morning_time = settings.get("morning_time", "08:00")
        dnd_enabled = settings.get("dnd_enabled", False)
        
        text = "🔔 Глобальные настройки напоминаний:\n\n"
        text += f"🔔 Общие напоминания: {'включены ✅' if reminders_enabled else 'выключены ❌'}\n"
        text += f"📅 Утреннее напоминание: {morning_time}\n"
        text += f"🌙 Режим \"Не беспокоить\": {'включен' if dnd_enabled else 'выключен'}"
        
        await call.message.edit_text(text, reply_markup=get_reminders_keyboard())
        await call.answer()
    except Exception as e:
        await call.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(lambda c: c.data == "reminders_disable_all")
async def disable_all_reminders(call: types.CallbackQuery):
    if not call.from_user:
        return await call.answer("❌ Ошибка", show_alert=True)
    
    user_id = call.from_user.id

    try:
        photo_url = await get_user_photo_url(call.bot, user_id)
        await api.put("/telegram/settings/reminders", {
            "telegram_id": user_id,
            "username": call.from_user.username,
            "first_name": call.from_user.first_name,
            "last_name": call.from_user.last_name,
            "photo_url": photo_url,
            "enabled": False
        })
        
        await call.message.edit_text(
            "❌ Все напоминания выключены",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="settings_reminders")]]
            )
        )
        await call.answer()
    except Exception as e:
        await call.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(lambda c: c.data == "settings_time")
async def show_time_settings(call: types.CallbackQuery):
    await call.message.edit_text(
        "Выбери время получения утренних напоминаний:",
        reply_markup=get_time_keyboard()
    )
    await call.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("time_set:"))
async def set_notification_time(call: types.CallbackQuery):
    if not call.data or not call.from_user:
        return await call.answer("❌ Ошибка", show_alert=True)
    
    time_str = call.data.split(":")[1] + ":" + call.data.split(":")[2]
    user_id = call.from_user.id

    try:
        photo_url = await get_user_photo_url(call.bot, user_id)
        await api.put("/telegram/settings/morning-time", {
            "telegram_id": user_id,
            "username": call.from_user.username,
            "first_name": call.from_user.first_name,
            "last_name": call.from_user.last_name,
            "photo_url": photo_url,
            "time": time_str
        })
        
        await call.message.edit_text(
            f"✅ Время уведомлений установлено: {time_str}\n\n"
            f"Добавить еще одно время?",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="➕ Добавить время", callback_data="time_custom")],
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="settings_main")]
                ]
            )
        )
        await call.answer()
    except Exception as e:
        await call.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(lambda c: c.data == "time_custom")
async def start_custom_time(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(SettingsStates.waiting_for_notification_time)
    
    await call.message.edit_text(
        "Введи время в формате ЧЧ:ММ (например, 08:30):",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Отмена", callback_data="settings_time")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ]
        )
    )
    await call.answer()


@router.message(SettingsStates.waiting_for_notification_time)
async def process_custom_time(message: types.Message, state: FSMContext):
    """Обработка введенного времени"""
    if not message.from_user:
        return
    
    # Проверяем, что это не команда меню
    menu_commands = [
        "🏠 Главное меню", "📅 Привычки на сегодня", "📊 Прогресс недели",
        "⚙️ Настройки", "👤 Личный кабинет", "🔄 Обновить список",
        "📋 Выбрать привычку", "🔄 Попробовать снова", "🆘 Помощь"
    ]
    
    if message.text in menu_commands:
        # Если это команда меню, очищаем состояние и не обрабатываем
        await state.clear()
        return
    
    # Проверяем, что message.text существует
    if not message.text:
        await message.answer("❌ Пожалуйста, введи время в формате ЧЧ:ММ")
        return
    
    time_pattern = re.compile(r'^([0-1]?[0-9]|2[0-3]):([0-5][0-9])$')
    if not time_pattern.match(message.text):
        await message.answer(
            "❌ Неверный формат времени\n\n"
            "Используй формат ЧЧ:ММ (например, 18:30)\n\n"
            "Или нажми '🔙 Отмена' для выхода."
        )
        return
    
    user_id = message.from_user.id

    try:
        photo_url = await get_user_photo_url(message.bot, user_id)
        await api.put("/telegram/settings/morning-time", {
            "telegram_id": user_id,
            "username": message.from_user.username,
            "first_name": message.from_user.first_name,
            "last_name": message.from_user.last_name,
            "photo_url": photo_url,
            "time": message.text
        })
        
        await message.answer(
            f"✅ Время уведомлений установлено: {message.text}",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="➕ Добавить время", callback_data="time_custom")],
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="settings_main")],
                    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
                ]
            )
        )
        await state.clear()
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


@router.callback_query(lambda c: c.data == "settings_dnd")
async def show_dnd_settings(call: types.CallbackQuery):
    if not call.from_user:
        return await call.answer("❌ Ошибка", show_alert=True)
    
    user_id = call.from_user.id

    try:
        photo_url = await get_user_photo_url(call.bot, user_id)
        data = await api.get("/telegram/settings", params={
            "telegram_id": user_id,
            "username": call.from_user.username,
            "first_name": call.from_user.first_name,
            "last_name": call.from_user.last_name,
            "photo_url": photo_url
        })
        settings = data.get("settings", {})
        dnd_enabled = settings.get("dnd_enabled", False)
        dnd_start = settings.get("dnd_start", "22:00")
        dnd_end = settings.get("dnd_end", "08:00")
        
        text = f"🌙 Режим \"Не беспокоить\" сейчас {'включен' if dnd_enabled else 'выключен'}\n\n"
        if dnd_enabled:
            text += f"Время: {dnd_start} - {dnd_end}\n"
        text += "Когда включен, бот не будет отправлять уведомления в указанное время."
        
        await call.message.edit_text(text, reply_markup=get_dnd_keyboard())
        await call.answer()
    except Exception as e:
        await call.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(lambda c: c.data == "dnd_enable")
async def enable_dnd(call: types.CallbackQuery):
    await call.message.edit_text(
        "Выбери период \"Не беспокоить\":",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🌙 Сейчас до завтра 08:00", callback_data="dnd_quick:tomorrow")],
                [InlineKeyboardButton(text="🌙 Каждый день: 22:00 - 08:00", callback_data="dnd_quick:daily")],
                [InlineKeyboardButton(text="🌙 Кастомное время", callback_data="dnd_custom")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="settings_dnd")]
            ]
        )
    )
    await call.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("dnd_quick:"))
async def set_quick_dnd(call: types.CallbackQuery):
    """Быстрая установка режима не беспокоить"""
    if not call.data or not call.from_user:
        return await call.answer("❌ Ошибка", show_alert=True)
    
    dnd_type = call.data.split(":")[1]
    user_id = call.from_user.id

    try:
        photo_url = await get_user_photo_url(call.bot, user_id)
        if dnd_type == "tomorrow":
            from datetime import timedelta
            end_time = (datetime.now() + timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0)
            await api.put("/telegram/settings/dnd", {
                "telegram_id": user_id,
                "username": call.from_user.username,
                "first_name": call.from_user.first_name,
                "last_name": call.from_user.last_name,
                "photo_url": photo_url,
                "enabled": True,
                "start": datetime.now().isoformat(),
                "end": end_time.isoformat()
            })
            await call.message.edit_text(
                "✅ Режим \"Не беспокоить\" включен\n"
                f"Время: сейчас - завтра 08:00\n"
                "Бот будет молчать в это время 🔕",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="settings_dnd")]]
                )
            )
        elif dnd_type == "daily":
            await api.put("/telegram/settings/dnd", {
                "telegram_id": user_id,
                "username": call.from_user.username,
                "first_name": call.from_user.first_name,
                "last_name": call.from_user.last_name,
                "photo_url": photo_url,
                "enabled": True,
                "start": "22:00",
                "end": "08:00",
                "daily": True
            })
            await call.message.edit_text(
                "✅ Режим \"Не беспокоить\" включен\n"
                "Время: 22:00 - 08:00 (каждый день)\n"
                "Бот будет молчать в это время 🔕",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="settings_dnd")]]
                )
            )
        
        await call.answer()
    except Exception as e:
        await call.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(lambda c: c.data == "dnd_custom")
async def start_custom_dnd(call: types.CallbackQuery, state: FSMContext):
    """Начало ввода кастомного времени для не беспокоить"""
    await state.set_state(SettingsStates.waiting_for_dnd_start)
    
    await call.message.edit_text(
        "Введи время начала (например, 22:00):",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Отмена", callback_data="settings_dnd")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ]
        )
    )
    await call.answer()


@router.message(SettingsStates.waiting_for_dnd_start)
async def process_dnd_start(message: types.Message, state: FSMContext):
    if not message.from_user:
        return
    
    # Проверяем, что это не команда меню
    menu_commands = [
        "🏠 Главное меню", "📅 Привычки на сегодня", "📊 Прогресс недели",
        "⚙️ Настройки", "👤 Личный кабинет", "🔄 Обновить список",
        "📋 Выбрать привычку", "🔄 Попробовать снова", "🆘 Помощь"
    ]
    
    if message.text in menu_commands:
        await state.clear()
        return
    
    # Проверяем, что message.text существует
    if not message.text:
        await message.answer("❌ Пожалуйста, введи время в формате ЧЧ:ММ")
        return
    
    time_pattern = re.compile(r'^([0-1]?[0-9]|2[0-3]):([0-5][0-9])$')
    if not time_pattern.match(message.text):
        await message.answer(
            "❌ Неверный формат времени\n\n"
            "Используй формат ЧЧ:ММ (например, 22:00)\n\n"
            "Или нажми '🔙 Отмена' для выхода."
        )
        return
    
    await state.update_data(dnd_start=message.text)
    await state.set_state(SettingsStates.waiting_for_dnd_end)
    await message.answer("Введи время окончания (например, 08:00):")


@router.message(SettingsStates.waiting_for_dnd_end)
async def process_dnd_end(message: types.Message, state: FSMContext):
    if not message.from_user:
        return
    
    # Проверяем, что это не команда меню
    menu_commands = [
        "🏠 Главное меню", "📅 Привычки на сегодня", "📊 Прогресс недели",
        "⚙️ Настройки", "👤 Личный кабинет", "🔄 Обновить список",
        "📋 Выбрать привычку", "🔄 Попробовать снова", "🆘 Помощь"
    ]
    
    if message.text in menu_commands:
        await state.clear()
        return
    
    # Проверяем, что message.text существует
    if not message.text:
        await message.answer("❌ Пожалуйста, введи время в формате ЧЧ:ММ")
        return
    
    time_pattern = re.compile(r'^([0-1]?[0-9]|2[0-3]):([0-5][0-9])$')
    if not time_pattern.match(message.text):
        await message.answer(
            "❌ Неверный формат времени\n\n"
            "Используй формат ЧЧ:ММ (например, 08:00)\n\n"
            "Или нажми '🔙 Отмена' для выхода."
        )
        return
    
    data = await state.get_data()
    dnd_start = data.get("dnd_start")
    user_id = message.from_user.id

    try:
        photo_url = await get_user_photo_url(message.bot, user_id)
        await api.put("/telegram/settings/dnd", {
            "telegram_id": user_id,
            "username": message.from_user.username,
            "first_name": message.from_user.first_name,
            "last_name": message.from_user.last_name,
            "photo_url": photo_url,
            "enabled": True,
            "start": dnd_start,
            "end": message.text
        })
        
        await message.answer(
            f"✅ Режим \"Не беспокоить\" включен\n"
            f"Время: {dnd_start} - {message.text}\n"
            "Бот будет молчать в это время 🔕",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="settings_dnd")],
                    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
                ]
            )
        )
        await state.clear()
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


@router.callback_query(lambda c: c.data == "dnd_disable")
async def disable_dnd(call: types.CallbackQuery):
    if not call.from_user:
        return await call.answer("❌ Ошибка", show_alert=True)
    
    user_id = call.from_user.id

    try:
        photo_url = await get_user_photo_url(call.bot, user_id)
        await api.put("/telegram/settings/dnd", {
            "telegram_id": user_id,
            "username": call.from_user.username,
            "first_name": call.from_user.first_name,
            "last_name": call.from_user.last_name,
            "photo_url": photo_url,
            "enabled": False
        })
        
        await call.message.edit_text(
            "❌ Режим \"Не беспокоить\" выключен",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="settings_dnd")]]
            )
        )
        await call.answer()
    except Exception as e:
        await call.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(lambda c: c.data == "reminders_habits")
async def show_habit_reminders(call: types.CallbackQuery):
    """Показ настроек напоминаний для конкретных привычек"""
    if not call.from_user:
        return await call.answer("❌ Ошибка", show_alert=True)
    
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
                "У тебя пока нет привычек для настройки",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="settings_reminders")]]
                )
            )
            return
        
        keyboard = []
        for habit in habits:
            habit_id = habit.get("id")
            name = habit.get("name", "Неизвестно")
            emoji = habit.get("emoji", "📌")
            keyboard.append([InlineKeyboardButton(
                text=f"{emoji} {name}",
                callback_data=f"habit_reminder:{habit_id}"
            )])
        keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="settings_reminders")])
        
        await call.message.edit_text(
            "🔔 Настройки напоминаний для привычек:\n\nВыбери привычку:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        await call.answer()
    except Exception as e:
        await call.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(lambda c: c.data and c.data.startswith("habit_reminder:"))
async def show_habit_reminder_settings(call: types.CallbackQuery):
    """Показ настроек напоминаний для конкретной привычки"""
    if not call.data or not call.from_user:
        return await call.answer("❌ Ошибка", show_alert=True)
    
    habit_id = call.data.split(":")[1]
    user_id = call.from_user.id

    try:
        photo_url = await get_user_photo_url(call.bot, user_id)
        habit_data = await api.get(f"/habits/{habit_id}", params={
            "telegram_id": user_id,
            "username": call.from_user.username,
            "first_name": call.from_user.first_name,
            "last_name": call.from_user.last_name,
            "photo_url": photo_url
        })
        habit = habit_data.get("habit", {})
        reminder_settings = habit.get("reminder_settings", {})
        
        name = habit.get("name", "Привычка")
        emoji = habit.get("emoji", "📌")
        enabled = reminder_settings.get("enabled", True)
        time = reminder_settings.get("time", "18:00")
        days = reminder_settings.get("days", ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"])
        
        text = f"🔔 Настройки для \"{emoji} {name}\":\n\n"
        text += f"🔔 Напоминания: {'включены ✅' if enabled else 'выключены ❌'}\n"
        text += f"🕓 Время: {time}\n"
        text += f"📅 Дни недели: {', '.join(days)}"
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="❌ Выключить" if enabled else "✅ Включить", 
                                    callback_data=f"habit_reminder_toggle:{habit_id}")],
                [InlineKeyboardButton(text="🕓 Изменить время", callback_data=f"habit_reminder_time:{habit_id}")],
                [InlineKeyboardButton(text="📅 Изменить дни", callback_data=f"habit_reminder_days:{habit_id}")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="reminders_habits")]
            ]
        )
        
        await call.message.edit_text(text, reply_markup=keyboard)
        await call.answer()
    except Exception as e:
        await call.answer(f"❌ Ошибка: {e}", show_alert=True)

