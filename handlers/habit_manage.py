from aiogram import Router, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.exceptions import TelegramBadRequest
from services.api import api
from keyboards.main_menu import main_menu
from handlers.start import get_user_photo_url

router = Router()


class HabitCreateStates(StatesGroup):
    waiting_for_title = State()
    waiting_for_type = State()
    waiting_for_value = State()
    waiting_for_unit = State()


def get_habit_type_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏱️ По времени (минуты, часы)", callback_data="habit_type:time")],
            [InlineKeyboardButton(text="🔢 По количеству (страницы, литры)", callback_data="habit_type:count")],
            [InlineKeyboardButton(text="✅ Да/Нет (выполнено/не выполнено)", callback_data="habit_type:boolean")],
            [InlineKeyboardButton(text="🔙 Отмена", callback_data="back_today")]
        ]
    )


@router.callback_query(lambda c: c.data == "habit_create")
async def start_create_habit(call: types.CallbackQuery, state: FSMContext):
    await call.answer()
    await state.set_state(HabitCreateStates.waiting_for_title)
    
    if call.message:
        await call.message.edit_text(
            "➕ Создание новой привычки\n\n"
            "Введи название привычки (например: Читать книгу, Пить воду):\n\n"
            "Или нажми '🔙 Отмена' для выхода.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Отмена", callback_data="back_today")],
                    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
                ]
            )
        )


@router.message(HabitCreateStates.waiting_for_title)
async def process_title(message: types.Message, state: FSMContext):
    if not message.from_user:
        return
    
    if not message.text:
        await message.answer("❌ Пожалуйста, введи название привычки")
        return
    
    menu_commands = [
        "🏠 Главное меню", "📅 Привычки на сегодня", "⚙️ Настройки",
        "👤 Личный кабинет", "🔄 Обновить список", "📋 Выбрать привычку"
    ]
    
    if message.text in menu_commands:
        await state.clear()
        return
    
    title = message.text.strip()
    if not title or len(title) < 2:
        await message.answer(
            "❌ Название слишком короткое\n\n"
            "Введи название привычки (минимум 2 символа):\n\n"
            "Или нажми '🔙 Отмена' для выхода."
        )
        return
    
    await state.update_data(title=title)
    await state.set_state(HabitCreateStates.waiting_for_type)
    
    await message.answer(
        f"📝 Название: {title}\n\n"
        "Выбери тип привычки:",
        reply_markup=get_habit_type_keyboard()
    )


@router.callback_query(lambda c: c.data and c.data.startswith("habit_type:"))
async def process_type(call: types.CallbackQuery, state: FSMContext):
    if not call.data:
        return await call.answer("❌ Ошибка", show_alert=True)
    
    habit_type = call.data.split(":")[1]
    await state.update_data(type=habit_type)
    
    if habit_type == "boolean":
        await state.update_data(value=1, unit="")
        await state.set_state(HabitCreateStates.waiting_for_unit)
        await finish_create_habit(call, state, call.bot)
    else:
        await state.set_state(HabitCreateStates.waiting_for_value)
        unit_hint = "минут" if habit_type == "time" else "страниц/литров/штук"
        await call.message.edit_text(
            f"📝 Название: {(await state.get_data()).get('title')}\n"
            f"📊 Тип: {'⏱️ По времени' if habit_type == 'time' else '🔢 По количеству'}\n\n"
            f"Введи целевое значение (например: 30 {unit_hint}):\n\n"
            "Или нажми '🔙 Отмена' для выхода.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Отмена", callback_data="back_today")],
                    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
                ]
            )
        )
        await call.answer()


@router.message(HabitCreateStates.waiting_for_value)
async def process_value(message: types.Message, state: FSMContext):
    if not message.from_user:
        return
    
    menu_commands = [
        "🏠 Главное меню", "📅 Привычки на сегодня", "⚙️ Настройки",
        "👤 Личный кабинет", "🔄 Обновить список", "📋 Выбрать привычку"
    ]
    
    # Проверяем, что message.text существует
    if not message.text:
        await message.answer("❌ Пожалуйста, введи название привычки")
        return
    
    if message.text in menu_commands:
        await state.clear()
        return
    
    try:
        value = int(message.text.strip())
        if value <= 0:
            raise ValueError("Значение должно быть положительным")
    except (ValueError, AttributeError):
        await message.answer(
            "❌ Некорректное значение\n\n"
            "Введи положительное целое число (например: 30, 50, 100):\n\n"
            "Или нажми '🔙 Отмена' для выхода."
        )
        return
    
    await state.update_data(value=value)
    await state.set_state(HabitCreateStates.waiting_for_unit)
    
    data = await state.get_data()
    habit_type = data.get("type", "count")
    
    # Кнопки для выбора единицы измерения в зависимости от типа
    if habit_type == "time":
        unit_buttons = [
            [InlineKeyboardButton(text="⏱️ Минут", callback_data="habit_unit:минут")],
            [InlineKeyboardButton(text="⏱️ Часов", callback_data="habit_unit:часов")],
            [InlineKeyboardButton(text="⏱️ Секунд", callback_data="habit_unit:секунд")],
            [InlineKeyboardButton(text="✏️ Своя единица", callback_data="habit_unit_custom")],
            [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="habit_unit_skip")],
            [InlineKeyboardButton(text="🔙 Отмена", callback_data="back_today")]
        ]
    else:  # count
        unit_buttons = [
            [InlineKeyboardButton(text="📄 Страниц", callback_data="habit_unit:страниц")],
            [InlineKeyboardButton(text="💧 Литров", callback_data="habit_unit:литров")],
            [InlineKeyboardButton(text="🔢 Штук", callback_data="habit_unit:штук")],
            [InlineKeyboardButton(text="👟 Шагов", callback_data="habit_unit:шагов")],
            [InlineKeyboardButton(text="📚 Слов", callback_data="habit_unit:слов")],
            [InlineKeyboardButton(text="✏️ Своя единица", callback_data="habit_unit_custom")],
            [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="habit_unit_skip")],
            [InlineKeyboardButton(text="🔙 Отмена", callback_data="back_today")]
        ]
    
    await message.answer(
        f"📝 Название: {data.get('title')}\n"
        f"📊 Тип: {'⏱️ По времени' if habit_type == 'time' else '🔢 По количеству'}\n"
        f"🎯 Цель: {value}\n\n"
        f"Выбери единицу измерения:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=unit_buttons)
    )


@router.callback_query(lambda c: c.data and c.data.startswith("habit_unit:"))
async def select_unit(call: types.CallbackQuery, state: FSMContext):
    if not call.data:
        return await call.answer("❌ Ошибка", show_alert=True)
    
    unit = call.data.split(":", 1)[1]
    await state.update_data(unit=unit)
    await finish_create_habit(call, state, call.bot)
    await call.answer()


@router.callback_query(lambda c: c.data == "habit_unit_custom")
async def custom_unit(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text(
        "✏️ Введи свою единицу измерения (например: км, калорий, раз):\n\n"
        "Или нажми '🔙 Отмена' для выхода.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Отмена", callback_data="back_today")]
            ]
        )
    )
    await call.answer()


@router.message(HabitCreateStates.waiting_for_unit)
async def process_unit(message: types.Message, state: FSMContext):
    if not message.from_user:
        return
    
    menu_commands = [
        "🏠 Главное меню", "📅 Привычки на сегодня", "⚙️ Настройки",
        "👤 Личный кабинет", "🔄 Обновить список", "📋 Выбрать привычку"
    ]
    
    if message.text in menu_commands:
        await state.clear()
        return
    
    unit = message.text.strip()
    if not unit:
        await message.answer("❌ Единица измерения не может быть пустой. Введи единицу:")
        return
    
    await state.update_data(unit=unit)
    await finish_create_habit_message(message, state, message.bot)


@router.callback_query(lambda c: c.data == "habit_unit_skip")
async def skip_unit(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(unit="")
    await finish_create_habit(call, state, call.bot)


async def finish_create_habit(call: types.CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    await create_habit_from_data(call.from_user, data, call.message, state, bot)


async def finish_create_habit_message(message: types.Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    await create_habit_from_data(message.from_user, data, message, state, bot)


async def create_habit_from_data(user: types.User, data: dict, message_or_call, state: FSMContext, bot: Bot):
    if not user:
        return
    
    user_id = user.id
    title = data.get("title")
    habit_type = data.get("type", "count")
    value = data.get("value", 1)
    unit = data.get("unit", "")
    
    photo_url = await get_user_photo_url(bot, user_id)
    
    try:
        result = await api.post("/habits/create", {
            "telegram_id": user_id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "photo_url": photo_url,
            "title": title,
            "type": habit_type,
            "value": value,
            "unit": unit,
            "is_active": True,
            "is_beneficial": True
        })
        
        habit = result.get("habit", {})
        name = habit.get("name", title)
        emoji = habit.get("emoji", "📌")
        
        text = f"✅ Привычка \"{emoji} {name}\" успешно создана!\n\n"
        if unit and value > 1:
            text += f"Цель: {value} {unit}"
        elif value > 1:
            text += f"Цель: {value}"
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📋 Посмотреть все привычки", callback_data="back_today")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ]
        )
        
        # Message нельзя редактировать, только CallbackQuery.message
        if isinstance(message_or_call, types.CallbackQuery) and message_or_call.message:
            try:
                await message_or_call.message.edit_text(text, reply_markup=keyboard)
            except TelegramBadRequest:
                await message_or_call.message.answer(text, reply_markup=keyboard)
        elif isinstance(message_or_call, types.Message):
            await message_or_call.answer(text, reply_markup=keyboard)
        else:
            if hasattr(message_or_call, 'answer'):
                await message_or_call.answer(text, reply_markup=keyboard)
        
        await state.clear()
    except Exception as e:
        error_text = f"❌ Ошибка при создании привычки: {e}"
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="habit_create")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="back_today")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ]
        )
        
        if isinstance(message_or_call, types.CallbackQuery) and message_or_call.message:
            try:
                await message_or_call.message.edit_text(error_text, reply_markup=keyboard)
            except TelegramBadRequest:
                await message_or_call.message.answer(error_text, reply_markup=keyboard)
        elif isinstance(message_or_call, types.Message):
            await message_or_call.answer(error_text, reply_markup=keyboard)
        else:
            if hasattr(message_or_call, 'answer'):
                await message_or_call.answer(error_text, reply_markup=keyboard)


@router.callback_query(lambda c: c.data and c.data.startswith("habit_delete:"))
async def delete_habit(call: types.CallbackQuery):
    if not call.data or not call.from_user:
        return await call.answer("❌ Ошибка", show_alert=True)
    
    habit_id = call.data.split(":")[1]
    user_id = call.from_user.id

    try:
        habit_data = await api.get(f"/habits/{habit_id}", params={
            "telegram_id": user_id,
            "username": call.from_user.username,
            "first_name": call.from_user.first_name,
            "last_name": call.from_user.last_name
        })
        habit = habit_data.get("habit", {})
        name = habit.get("name", "Привычка")
        emoji = habit.get("emoji", "📌")
        
        await call.message.edit_text(
            f"🗑️ Удаление привычки\n\n"
            f"Ты уверен, что хочешь удалить привычку:\n"
            f"{emoji} {name}?\n\n"
            f"Это действие нельзя отменить!",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"habit_delete_confirm:{habit_id}")],
                    [InlineKeyboardButton(text="❌ Отмена", callback_data=f"habit_select:{habit_id}")]
                ]
            )
        )
        await call.answer()
    except Exception as e:
        await call.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(lambda c: c.data and c.data.startswith("habit_delete_confirm:"))
async def confirm_delete_habit(call: types.CallbackQuery):
    if not call.data or not call.from_user:
        return await call.answer("❌ Ошибка", show_alert=True)
    
    habit_id = call.data.split(":")[1]
    user_id = call.from_user.id
    
    try:
        await api.delete(f"/habits/delete/{habit_id}", params={
            "telegram_id": user_id,
            "username": call.from_user.username,
            "first_name": call.from_user.first_name,
            "last_name": call.from_user.last_name
        })
        
        await call.message.edit_text(
            "✅ Привычка успешно удалена!",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="📋 К списку привычек", callback_data="back_today")],
                    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
                ]
            )
        )
        await call.answer("✅ Привычка удалена")
    except Exception as e:
        await call.answer(f"❌ Ошибка: {e}", show_alert=True)

