from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from services.api import api
from utils.helpers import get_user_photo_url
import logging

logger = logging.getLogger(__name__)

router = Router()


class HabitCompleteStates(StatesGroup):
    waiting_for_amount = State()


def get_complete_keyboard(habit_id: int, has_quantity: bool):
    keyboard = []
    if has_quantity:
        keyboard.append([InlineKeyboardButton(text="📝 Ввести вручную", callback_data=f"habit_input:{habit_id}")])
        keyboard.append([InlineKeyboardButton(text="✅ Отметить полным выполнением", callback_data=f"habit_full:{habit_id}")])
    else:
        keyboard.append([InlineKeyboardButton(text="✅ Выполнить", callback_data=f"habit_full:{habit_id}")])
    keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"habit_select:{habit_id}")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


@router.callback_query(lambda c: c.data and c.data.startswith("habit_complete:"))
async def start_complete_habit(call: types.CallbackQuery):
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
        habit_type = habit.get("type", "boolean")
        
        has_quantity = habit_type == "quantity"
        
        if not unit or unit.strip() == "":
            if goal <= 1:
                has_quantity = False
        
        if not has_quantity:
            await complete_habit_boolean(call, habit_id, user_id, habit, photo_url)
            return
        text = f"📝 <b>{name}</b>\n"
        text += f"📊 Цель: {goal} {unit}\n"
        text += f"📈 Текущий прогресс: {progress} / {goal} {unit}\n\n"
        text += "💬 <b>Введи количество</b> (можно использовать дробные числа):"
        await call.message.edit_text(text, reply_markup=get_complete_keyboard(habit_id, True), parse_mode="HTML")
        await call.answer()
    except Exception as e:
        await call.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(lambda c: c.data and c.data.startswith("habit_input:"))
async def start_input_amount(call: types.CallbackQuery, state: FSMContext):
    if not call.data:
        return await call.answer("❌ Ошибка", show_alert=True)
    
    habit_id = call.data.split(":")[1]
    await state.update_data(habit_id=habit_id)
    await state.set_state(HabitCompleteStates.waiting_for_amount)
    
    await call.message.edit_text(
        "💬 <b>Введи количество</b>\n\n"
        "Например: <code>0.5</code>, <code>1</code>, <code>2.5</code>\n\n"
        "Или нажми '🔙 Отмена' для выхода.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Отмена", callback_data=f"habit_select:{habit_id}")]
            ]
        ),
        parse_mode="HTML"
    )
    await call.answer()


@router.message(HabitCompleteStates.waiting_for_amount)
async def process_amount_input(message: types.Message, state: FSMContext):
    if not message.from_user:
        return
    
    menu_commands = [
        "🏠 Главное меню", "📅 Привычки",
        "⚙️ Настройки", "👤 Личный кабинет", "🔄 Обновить список",
        "📋 Выбрать привычку", "🔄 Попробовать снова", "🆘 Помощь"
    ]
    
    if not message.text:
        await message.answer("❌ Пожалуйста, введи число")
        return
    
    if message.text in menu_commands:
        await state.clear()
        return
    
    text_clean = message.text.replace(",", ".").replace(" ", "")
    if not text_clean.replace(".", "").replace("-", "").isdigit():
        await message.answer(
            "❌ Некорректное значение\n\n"
            "Введи положительное число (например, 20 или 1.5):\n\n"
            "Или нажми '🔙 Отмена' для выхода."
        )
        return
    
    try:
        amount = float(message.text.replace(",", "."))
        if amount <= 0:
            raise ValueError("Число должно быть положительным")
    except (ValueError, AttributeError):
        await message.answer(
            "❌ Некорректное значение\n\n"
            "Введи положительное число (например, 20 или 1.5):\n\n"
            "Или нажми '🔙 Отмена' для выхода."
        )
        return
    
    data = await state.get_data()
    habit_id = data.get("habit_id")
    user_id = message.from_user.id
    
    photo_url = await get_user_photo_url(message.bot, user_id)
    send_amount = amount
    try:
        habit_data = await api.get(f"/habits/{habit_id}", params={
            "telegram_id": user_id,
            "username": message.from_user.username,
            "first_name": message.from_user.first_name,
            "last_name": message.from_user.last_name,
            "photo_url": photo_url
        })
        habit = habit_data.get("habit", {})
        unit = habit.get("unit", "")
        
        if unit == "часов":
            send_amount = amount * 60
    except Exception:
        pass
    
    try:
        result = await api.post("/habits/complete", {
            "telegram_id": user_id,
            "username": message.from_user.username,
            "first_name": message.from_user.first_name,
            "last_name": message.from_user.last_name,
            "photo_url": photo_url,
            "habit_id": int(habit_id),
            "amount": send_amount
        })
        
        habit_data = result.get("habit", {})
        name = habit_data.get("name", "Привычка")
        progress = habit_data.get("progress", 0)
        goal = habit_data.get("goal", 0)
        unit = habit_data.get("unit", "")
        completed = habit_data.get("completed", False)
        streak = result.get("streak", 0)
        
        text = f"✅ <b>Добавлено {amount} {unit}!</b>\n\n"
        if goal > 0:
            percentage = int(progress/goal*100)
            text += f"📊 Прогресс: <b>{progress} / {goal} {unit}</b> ({percentage}%)\n"
        else:
            text += f"📊 Прогресс: <b>{progress} / {goal} {unit}</b>\n"
        
        if completed:
            text += "\n🎉 <b>Привычка выполнена!</b>"
            if streak > 0:
                text += f"\n🔥 Текущая серия: <b>{streak} дней</b> подряд"
        
        keyboard_buttons = [
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_today")]
        ]
        
        if completed:
            keyboard_buttons.insert(0, [InlineKeyboardButton(text="❌ Отменить выполнение", callback_data=f"habit_undo:{habit_id}")])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        await state.clear()
    except Exception as e:
        await message.answer(
            f"❌ Произошла ошибка\n\n"
            f"Не удалось сохранить выполнение привычки.\n"
            f"Пожалуйста, попробуй еще раз.",
            reply_markup=types.ReplyKeyboardMarkup(
                keyboard=[
                    [types.KeyboardButton(text="🔄 Попробовать снова")],
                    [types.KeyboardButton(text="🆘 Помощь")]
                ],
                resize_keyboard=True
            )
        )


@router.callback_query(lambda c: c.data and c.data.startswith("habit_full:"))
async def complete_habit_full(call: types.CallbackQuery):
    if not call.data:
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
        habit_type = habit.get("type", "boolean")
        
        if habit_type == "quantity":
            goal = habit.get("goal", 0)
            unit = habit.get("unit", "")
            
            send_goal = goal
            if unit == "часов":
                send_goal = goal * 60
            
            result = await api.post("/habits/complete", {
                "telegram_id": user_id,
                "username": call.from_user.username,
                "first_name": call.from_user.first_name,
                "last_name": call.from_user.last_name,
                "photo_url": photo_url,
                "habit_id": int(habit_id),
                "amount": send_goal
            })
            
            name = habit.get("name", "Привычка")
            progress = result.get("habit", {}).get("progress", 0)
            goal = result.get("habit", {}).get("goal", 0)
            unit = result.get("habit", {}).get("unit", "")
            completed = result.get("habit", {}).get("completed", False)
            streak = result.get("streak", 0)
            
            text = f"✅ <b>Привычка \"{name}\" выполнена полностью!</b>\n\n"
            text += f"📊 Прогресс: <b>{progress} / {goal} {unit}</b> (100%)\n"
            
            if streak > 0:
                text += f"🔥 Текущая серия: <b>{streak} дней</b> подряд"
            
            keyboard_buttons = [
                [InlineKeyboardButton(text="🔙 Назад", callback_data="back_today")]
            ]
            
            if completed:
                keyboard_buttons.insert(0, [InlineKeyboardButton(text="❌ Отменить выполнение", callback_data=f"habit_undo:{habit_id}")])
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
            await call.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
            await call.answer("🎉 Готово!")
        else:
            await complete_habit_boolean(call, habit_id, user_id, habit, photo_url)
    except Exception as e:
        await call.answer(f"❌ Ошибка: {e}", show_alert=True)


async def complete_habit_boolean(call: types.CallbackQuery, habit_id: str, user_id: int, habit: dict, photo_url: str = None):
    try:
        if not photo_url or not photo_url.strip():
            photo_url = await get_user_photo_url(call.bot, user_id)
        
        if not call.from_user:
            logger.error(f"call.from_user is None для user_id={user_id}")
            await call.answer("❌ Ошибка: не удалось определить пользователя", show_alert=True)
            return
        
        result = await api.post("/habits/complete", {
            "telegram_id": user_id,
            "username": call.from_user.username,
            "first_name": call.from_user.first_name,
            "last_name": call.from_user.last_name,
            "photo_url": photo_url,
            "habit_id": int(habit_id)
        })
        
        name = habit.get("name", "Привычка")
        streak = result.get("streak", 0)
        
        text = f"✅ <b>Привычка \"{name}\" выполнена!</b>\n\n"
        if streak > 0:
            text += f"🔥 Текущая серия: <b>{streak} дней</b> подряд"
        else:
            text += "🎉 Отличная работа!"
        
        habit_data = await api.get(f"/habits/{habit_id}", params={
            "telegram_id": user_id,
            "username": call.from_user.username,
            "first_name": call.from_user.first_name,
            "last_name": call.from_user.last_name,
            "photo_url": photo_url
        })
        habit = habit_data.get("habit", {})
        completed = habit.get("completed", False)
        
        keyboard_buttons = [
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_today")]
        ]
        
        if completed:
            keyboard_buttons.insert(0, [InlineKeyboardButton(text="❌ Отменить выполнение", callback_data=f"habit_undo:{habit_id}")])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        await call.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await call.answer("🎉 Готово!")
    except Exception as e:
        await call.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(lambda c: c.data and c.data.startswith("habit_undo:"))
async def undo_habit_completion(call: types.CallbackQuery):
    if not call.data or not call.from_user:
        return await call.answer("❌ Ошибка", show_alert=True)
    
    habit_id = call.data.split(":")[1]
    user_id = call.from_user.id

    try:
        photo_url = await get_user_photo_url(call.bot, user_id)
        result = await api.post("/habits/undo", {
            "telegram_id": user_id,
            "username": call.from_user.username,
            "first_name": call.from_user.first_name,
            "last_name": call.from_user.last_name,
            "photo_url": photo_url,
            "habit_id": int(habit_id)
        })
        
        habit_data = result.get("habit", {})
        name = habit_data.get("name", "Привычка")
        progress = habit_data.get("progress", 0)
        goal = habit_data.get("goal", 0)
        unit = habit_data.get("unit", "")
        streak = result.get("streak", 0)
        
        text = f"❌ <b>Выполнение привычки \"{name}\" отменено</b>\n\n"
        if unit and goal > 0:
            text += f"📊 Прогресс: <b>{progress} / {goal} {unit}</b>\n"
        if streak > 0:
            text += f"🔥 Текущая серия: <b>{streak} дней</b>"
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="back_today")]
            ]
        )
        
        await call.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await call.answer("✅ Выполнение отменено")
    except Exception as e:
        await call.answer(f"❌ Ошибка: {e}", show_alert=True)

