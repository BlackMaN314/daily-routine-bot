from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from services.api import api
from keyboards.main_menu import main_menu
from utils.helpers import get_user_photo_url
import re

router = Router()


class SettingsStates(StatesGroup):
    waiting_for_notification_time = State()
    waiting_for_edit_time = State()


def get_settings_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔔 Напоминания", callback_data="settings_reminders")],
            [InlineKeyboardButton(text="🌙 Не беспокоить", callback_data="settings_dnd")]
        ]
    )


def get_reminders_keyboard(notify_times: list = None):
    if notify_times is None:
        notify_times = []
    
    keyboard = []
    
    if notify_times:
        time_buttons = []
        for time_str in notify_times:
            time_buttons.append(InlineKeyboardButton(
                text=f"🕓 {time_str}",
                callback_data=f"time_settings:{time_str}"
            ))
        keyboard.append(time_buttons)
    
    keyboard.append([
        InlineKeyboardButton(text="➕ Добавить время", callback_data="time_add"),
        InlineKeyboardButton(text="🔙 Назад", callback_data="settings_main")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_dnd_keyboard(dnd_enabled: bool = False):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="✅ Включить" if not dnd_enabled else "❌ Выключить",
                callback_data="dnd_enable" if not dnd_enabled else "dnd_disable"
            )],
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
        
        text = "⚙️ <b>Настройки</b>\n\n"
        text += "Выбери, что хочешь изменить 👇"
        
        await message.answer(text, reply_markup=get_settings_keyboard(), parse_mode="HTML")
    except Exception as e:
        await message.answer(
            f"❌ Ошибка при загрузке настроек: {e}",
            reply_markup=main_menu()
        )


@router.callback_query(lambda c: c.data == "settings_main")
async def settings_main(call: types.CallbackQuery):
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
        
        notify_times = settings.get("notify_times", [])
        dnd_enabled = settings.get("dnd_enabled", False)
        
        text = "🔔 Глобальные настройки напоминаний:\n\n"
        if notify_times:
            text += f"📅 Времена уведомлений: {', '.join(notify_times)}\n"
        else:
            text += "📅 Времена уведомлений: не заданы\n"
        text += f"🌙 Режим \"Не беспокоить\": {'включен' if dnd_enabled else 'выключен'}"
        
        await call.message.edit_text(text, reply_markup=get_reminders_keyboard(notify_times))
        await call.answer()
    except Exception as e:
        await call.answer(f"❌ Ошибка: {e}", show_alert=True)


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
        
        text = f"🌙 Режим \"Не беспокоить\" сейчас {'включен ✅' if dnd_enabled else 'выключен ❌'}"
        
        await call.message.edit_text(text, reply_markup=get_dnd_keyboard(dnd_enabled))
        await call.answer()
    except Exception as e:
        await call.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(lambda c: c.data == "dnd_enable")
async def enable_dnd(call: types.CallbackQuery):
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
            "enabled": True
        })
        
        data = await api.get("/telegram/settings", params={
            "telegram_id": user_id,
            "username": call.from_user.username,
            "first_name": call.from_user.first_name,
            "last_name": call.from_user.last_name,
            "photo_url": photo_url
        })
        settings = data.get("settings", {})
        dnd_enabled = settings.get("dnd_enabled", False)
        
        text = f"🌙 Режим \"Не беспокоить\" сейчас {'включен ✅' if dnd_enabled else 'выключен ❌'}"
        
        await call.message.edit_text(text, reply_markup=get_dnd_keyboard(dnd_enabled))
        await call.answer()
    except Exception as e:
        await call.answer(f"❌ Ошибка: {e}", show_alert=True)


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
        
        data = await api.get("/telegram/settings", params={
            "telegram_id": user_id,
            "username": call.from_user.username,
            "first_name": call.from_user.first_name,
            "last_name": call.from_user.last_name,
            "photo_url": photo_url
        })
        settings = data.get("settings", {})
        dnd_enabled = settings.get("dnd_enabled", False)
        
        text = f"🌙 Режим \"Не беспокоить\" сейчас {'включен ✅' if dnd_enabled else 'выключен ❌'}"
        
        await call.message.edit_text(text, reply_markup=get_dnd_keyboard(dnd_enabled))
        await call.answer()
    except Exception as e:
        await call.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(lambda c: c.data == "time_add")
async def add_notification_time(call: types.CallbackQuery, state: FSMContext):
    if not call.from_user:
        return await call.answer("❌ Ошибка", show_alert=True)
    
    await state.set_state(SettingsStates.waiting_for_notification_time)
    
    await call.message.edit_text(
        "🕓 <b>Добавить время уведомления</b>\n\n"
        "Введи время в формате <code>ЧЧ:ММ</code>\n"
        "Например: <code>08:00</code>, <code>18:30</code>\n\n"
        "Или нажми '🔙 Отмена' для выхода.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Отмена", callback_data="settings_reminders")]
            ]
        ),
        parse_mode="HTML"
    )
    await call.answer()


@router.message(SettingsStates.waiting_for_notification_time)
async def process_notification_time(message: types.Message, state: FSMContext):
    if not message.from_user:
        return
    
    menu_commands = [
        "🏠 Главное меню", "📅 Привычки",
        "⚙️ Настройки", "👤 Личный кабинет", "🔄 Обновить список",
        "📋 Выбрать привычку", "🔄 Попробовать снова", "🆘 Помощь"
    ]
    
    if message.text in menu_commands:
        await state.clear()
        return
    
    if not message.text:
        await message.answer("❌ Пожалуйста, введи время в формате ЧЧ:ММ")
        return
    
    time_pattern = re.compile(r'^([0-1]?[0-9]|2[0-3]):([0-5][0-9])$')
    if not time_pattern.match(message.text.strip()):
        await message.answer(
            "❌ Неверный формат времени\n\n"
            "Используй формат <code>ЧЧ:ММ</code> (например, 08:00, 18:30)\n\n"
            "Или нажми '🔙 Отмена' для выхода.",
            parse_mode="HTML"
        )
        return
    
    time_str = message.text.strip()
    user_id = message.from_user.id

    try:
        photo_url = await get_user_photo_url(message.bot, user_id)
        await api.put("/telegram/settings/morning-time", {
            "telegram_id": user_id,
            "username": message.from_user.username,
            "first_name": message.from_user.first_name,
            "last_name": message.from_user.last_name,
            "photo_url": photo_url,
            "time": time_str
        })
        
        data = await api.get("/telegram/settings", params={
            "telegram_id": user_id,
            "username": message.from_user.username,
            "first_name": message.from_user.first_name,
            "last_name": message.from_user.last_name,
            "photo_url": photo_url
        })
        settings = data.get("settings", {})
        notify_times = settings.get("notify_times", [])
        dnd_enabled = settings.get("dnd_enabled", False)
        
        text = "🔔 Глобальные настройки напоминаний:\n\n"
        if notify_times:
            text += f"📅 Времена уведомлений: {', '.join(notify_times)}\n"
        else:
            text += "📅 Времена уведомлений: не заданы\n"
        text += f"🌙 Режим \"Не беспокоить\": {'включен' if dnd_enabled else 'выключен'}"
        
        await message.answer(
            f"✅ Время <code>{time_str}</code> добавлено!",
            reply_markup=get_reminders_keyboard(notify_times),
            parse_mode="HTML"
        )
        await state.clear()
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


def get_time_settings_keyboard(time_str: str):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Изменить", callback_data=f"time_edit:{time_str}")],
            [InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"time_remove:{time_str}")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="settings_reminders")]
        ]
    )


@router.callback_query(lambda c: c.data and c.data.startswith("time_settings:"))
async def show_time_settings(call: types.CallbackQuery):
    if not call.data or not call.from_user:
        return await call.answer("❌ Ошибка", show_alert=True)
    
    time_str = call.data.split(":", 1)[1]
    
    await call.message.edit_text(
        f"🕓 <b>Настройки времени уведомления</b>\n\n"
        f"Время: <code>{time_str}</code>\n\n"
        "Выбери действие:",
        reply_markup=get_time_settings_keyboard(time_str),
        parse_mode="HTML"
    )
    await call.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("time_edit:"))
async def edit_notification_time(call: types.CallbackQuery, state: FSMContext):
    if not call.data or not call.from_user:
        return await call.answer("❌ Ошибка", show_alert=True)
    
    old_time_str = call.data.split(":", 1)[1]
    await state.update_data(old_time=old_time_str)
    await state.set_state(SettingsStates.waiting_for_edit_time)
    
    await call.message.edit_text(
        f"✏️ <b>Изменение времени уведомления</b>\n\n"
        f"Текущее время: <code>{old_time_str}</code>\n\n"
        "Введи новое время в формате <code>ЧЧ:ММ</code>\n"
        "Например: <code>08:00</code>, <code>18:30</code>\n\n"
        "Или нажми '🔙 Отмена' для выхода.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Отмена", callback_data=f"time_settings:{old_time_str}")]
            ]
        ),
        parse_mode="HTML"
    )
    await call.answer()


@router.message(SettingsStates.waiting_for_edit_time)
async def process_edit_time(message: types.Message, state: FSMContext):
    if not message.from_user:
        return
    
    menu_commands = [
        "🏠 Главное меню", "📅 Привычки",
        "⚙️ Настройки", "👤 Личный кабинет", "🔄 Обновить список",
        "📋 Выбрать привычку", "🔄 Попробовать снова", "🆘 Помощь"
    ]
    
    if message.text in menu_commands:
        await state.clear()
        return
    
    if not message.text:
        await message.answer("❌ Пожалуйста, введи время в формате ЧЧ:ММ")
        return
    
    time_pattern = re.compile(r'^([0-1]?[0-9]|2[0-3]):([0-5][0-9])$')
    if not time_pattern.match(message.text.strip()):
        await message.answer(
            "❌ Неверный формат времени\n\n"
            "Используй формат <code>ЧЧ:ММ</code> (например, 08:00, 18:30)\n\n"
            "Или нажми '🔙 Отмена' для выхода.",
            parse_mode="HTML"
        )
        return
    
    new_time_str = message.text.strip()
    data = await state.get_data()
    old_time_str = data.get("old_time")
    user_id = message.from_user.id

    try:
        photo_url = await get_user_photo_url(message.bot, user_id)
        settings_data = await api.get("/telegram/settings", params={
            "telegram_id": user_id,
            "username": message.from_user.username,
            "first_name": message.from_user.first_name,
            "last_name": message.from_user.last_name,
            "photo_url": photo_url
        })
        settings = settings_data.get("settings", {})
        notify_times = settings.get("notify_times", [])
        
        if old_time_str in notify_times:
            notify_times.remove(old_time_str)
        
        if new_time_str not in notify_times:
            notify_times.append(new_time_str)
        
        await api.put("/telegram/settings/notify-times", {
            "telegram_id": user_id,
            "username": message.from_user.username,
            "first_name": message.from_user.first_name,
            "last_name": message.from_user.last_name,
            "photo_url": photo_url,
            "notify_times": notify_times
        })
        
        settings_data = await api.get("/telegram/settings", params={
            "telegram_id": user_id,
            "username": message.from_user.username,
            "first_name": message.from_user.first_name,
            "last_name": message.from_user.last_name,
            "photo_url": photo_url
        })
        settings = settings_data.get("settings", {})
        notify_times = settings.get("notify_times", [])
        dnd_enabled = settings.get("dnd_enabled", False)
        
        text = "🔔 Глобальные настройки напоминаний:\n\n"
        if notify_times:
            text += f"📅 Времена уведомлений: {', '.join(notify_times)}\n"
        else:
            text += "📅 Времена уведомлений: не заданы\n"
        text += f"🌙 Режим \"Не беспокоить\": {'включен' if dnd_enabled else 'выключен'}"
        
        await message.answer(
            f"✅ Время изменено с <code>{old_time_str}</code> на <code>{new_time_str}</code>!",
            reply_markup=get_reminders_keyboard(notify_times),
            parse_mode="HTML"
        )
        await state.clear()
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


@router.callback_query(lambda c: c.data and c.data.startswith("time_remove:"))
async def remove_notification_time(call: types.CallbackQuery):
    if not call.data or not call.from_user:
        return await call.answer("❌ Ошибка", show_alert=True)
    
    time_str = call.data.split(":", 1)[1]
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
        notify_times = settings.get("notify_times", [])
        
        if time_str in notify_times:
            notify_times.remove(time_str)
            
            await api.put("/telegram/settings/notify-times", {
                "telegram_id": user_id,
                "username": call.from_user.username,
                "first_name": call.from_user.first_name,
                "last_name": call.from_user.last_name,
                "photo_url": photo_url,
                "notify_times": notify_times
            })
        
        data = await api.get("/telegram/settings", params={
            "telegram_id": user_id,
            "username": call.from_user.username,
            "first_name": call.from_user.first_name,
            "last_name": call.from_user.last_name,
            "photo_url": photo_url
        })
        settings = data.get("settings", {})
        notify_times = settings.get("notify_times", [])
        dnd_enabled = settings.get("dnd_enabled", False)
        
        text = "🔔 Глобальные настройки напоминаний:\n\n"
        if notify_times:
            text += f"📅 Времена уведомлений: {', '.join(notify_times)}\n"
        else:
            text += "📅 Времена уведомлений: не заданы\n"
        text += f"🌙 Режим \"Не беспокоить\": {'включен' if dnd_enabled else 'выключен'}"
        
        await call.message.edit_text(text, reply_markup=get_reminders_keyboard(notify_times))
        await call.answer(f"✅ Время {time_str} удалено")
    except Exception as e:
        await call.answer(f"❌ Ошибка: {e}", show_alert=True)


