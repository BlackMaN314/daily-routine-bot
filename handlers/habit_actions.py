from aiogram import Router, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from services.api import api
from keyboards.main_menu import main_menu
from handlers.start import get_user_photo_url
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
    keyboard.append([InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_stats_period_keyboard(habit_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📅 Неделя", callback_data=f"stats_period:{habit_id}:week")],
            [InlineKeyboardButton(text="📆 Месяц", callback_data=f"stats_period:{habit_id}:month")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data=f"habit_select:{habit_id}")]
        ]
    )


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
        habit_type = habit.get("type", "boolean")  # "quantity" or "boolean"
        emoji = habit.get("emoji", "📌")
        
        has_quantity = habit_type == "quantity" and goal > 0
        
        if has_quantity:
            text = f"{emoji} {name} {goal} {unit}\n"
            text += f"Текущий прогресс: {progress} / {goal} {unit}\n\n"
            text += "Введи количество (можно использовать дробные числа):"
            await call.message.edit_text(text, reply_markup=get_complete_keyboard(habit_id, True))
        else:
            await complete_habit_boolean(call, habit_id, user_id, habit, photo_url)
        
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
        "Введи количество (например: 0.5, 1, 2.5):\n\n"
        "Или нажми '🔙 Отмена' для выхода.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Отмена", callback_data=f"habit_select:{habit_id}")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ]
        )
    )
    await call.answer()


@router.message(HabitCompleteStates.waiting_for_amount)
async def process_amount_input(message: types.Message, state: FSMContext):
    if not message.from_user:
        return
    
    menu_commands = [
        "🏠 Главное меню", "📅 Привычки на сегодня", "📊 Прогресс недели",
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
    
    try:
        photo_url = await get_user_photo_url(message.bot, user_id)
        result = await api.post("/habits/complete", {
            "telegram_id": user_id,
            "username": message.from_user.username,
            "first_name": message.from_user.first_name,
            "last_name": message.from_user.last_name,
            "photo_url": photo_url,
            "habit_id": int(habit_id),
            "amount": amount
        })
        
        habit_data = result.get("habit", {})
        name = habit_data.get("name", "Привычка")
        progress = habit_data.get("progress", 0)
        goal = habit_data.get("goal", 0)
        unit = habit_data.get("unit", "")
        completed = habit_data.get("completed", False)
        streak = result.get("streak", 0)
        emoji = habit_data.get("emoji", "📌")
        
        text = f"✅ Добавлено {amount} {unit}!\n"
        text += f"Прогресс: {progress} / {goal} {unit} ({int(progress/goal*100)}%)"
        
        if completed:
            text += " ✅\nПривычка выполнена! 🎉"
            if streak > 0:
                text += f"\nТекущая серия: {streak} дней подряд 🔥"
        
        keyboard_buttons = [
            [InlineKeyboardButton(text="🔄 Назад к списку", callback_data="back_today")]
        ]
        
        if completed:
            keyboard_buttons.insert(0, [InlineKeyboardButton(text="❌ Отменить выполнение", callback_data=f"habit_undo:{habit_id}")])
        
        keyboard_buttons.append([InlineKeyboardButton(text="📅 Главное меню", callback_data="main_menu")])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        await message.answer(text, reply_markup=keyboard)
        await state.clear()
    except Exception as e:
        await message.answer(
            f"❌ Произошла ошибка\n\n"
            f"Не удалось сохранить выполнение привычки.\n"
            f"Пожалуйста, попробуй еще раз.",
            reply_markup=types.ReplyKeyboardMarkup(
                keyboard=[
                    [types.KeyboardButton(text="🔄 Попробовать снова")],
                    [types.KeyboardButton(text="🆘 Помощь")],
                    [types.KeyboardButton(text="🔙 Главное меню")]
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
        emoji = habit.get("emoji", "📌")
        
        text = f"✅ Привычка \"{name}\" выполнена!\n"
        if streak > 0:
            text += f"Текущая серия: {streak} дней подряд 🔥"
        
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
            [InlineKeyboardButton(text="🔄 Назад к списку", callback_data="back_today")]
        ]
        
        if completed:
            keyboard_buttons.insert(0, [InlineKeyboardButton(text="❌ Отменить выполнение", callback_data=f"habit_undo:{habit_id}")])
        
        keyboard_buttons.append([InlineKeyboardButton(text="📅 Главное меню", callback_data="main_menu")])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        await call.message.edit_text(text, reply_markup=keyboard)
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
        # Отменяем выполнение привычки
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
        emoji = habit_data.get("emoji", "📌")
        progress = habit_data.get("progress", 0)
        goal = habit_data.get("goal", 0)
        unit = habit_data.get("unit", "")
        streak = result.get("streak", 0)
        
        text = f"❌ Выполнение привычки \"{emoji} {name}\" отменено\n\n"
        if unit and goal > 0:
            text += f"Прогресс: {progress} / {goal} {unit}"
        if streak > 0:
            text += f"\nТекущая серия: {streak} дней 🔥"
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Назад к списку", callback_data="back_today")],
                [InlineKeyboardButton(text="📅 Главное меню", callback_data="main_menu")]
            ]
        )
        
        await call.message.edit_text(text, reply_markup=keyboard)
        await call.answer("✅ Выполнение отменено")
    except Exception as e:
        await call.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(lambda c: c.data and c.data.startswith("habit_stats:"))
async def show_habit_stats(call: types.CallbackQuery):
    if not call.data:
        return await call.answer("❌ Ошибка", show_alert=True)
    
    habit_id = call.data.split(":")[1]
    user_id = call.from_user.id

    try:
        photo_url = await get_user_photo_url(call.bot, user_id)
        data = await api.get(f"/habits/{habit_id}/stats", params={
            "telegram_id": user_id,
            "username": call.from_user.username,
            "first_name": call.from_user.first_name,
            "last_name": call.from_user.last_name,
            "photo_url": photo_url,
            "period": "week"
        })
        stats = data.get("stats", {})
        habit = data.get("habit", {})
        
        name = habit.get("name", "Привычка")
        emoji = habit.get("emoji", "📌")
        completed = stats.get("completed", 0)
        total = stats.get("total", 7)
        streak = stats.get("current_streak", 0)
        best_streak = stats.get("best_streak", 0)
        last_completed = stats.get("last_completed")
        avg_frequency = stats.get("avg_frequency", 0)
        
        percentage = int((completed / total * 100)) if total > 0 else 0
        
        text = f"📈 Привычка: {emoji} {name}\n"
        text += f"Выполнено: {completed} из {total} ({percentage}%)\n"
        text += f"Серия: {streak} дней 🔥\n"
        text += f"Лучшая серия: {best_streak} дней (макс.)\n"
        
        if last_completed:
            text += f"Последний раз: {last_completed}\n"
        
        if avg_frequency > 0:
            text += f"Средняя частота: {avg_frequency:.1f} раза/неделю"
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📊 Детальная история", callback_data=f"stats_detail:{habit_id}")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data=f"habit_select:{habit_id}")],
                [InlineKeyboardButton(text="📅 Главное меню", callback_data="main_menu")]
            ]
        )
        
        await call.message.edit_text(text, reply_markup=keyboard)
        await call.answer()
    except Exception as e:
        await call.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(lambda c: c.data and c.data.startswith("stats_detail:"))
async def show_stats_detail(call: types.CallbackQuery):
    if not call.data:
        return await call.answer("❌ Ошибка", show_alert=True)
    
    habit_id = call.data.split(":")[1]
    user_id = call.from_user.id

    try:
        photo_url = await get_user_photo_url(call.bot, user_id)
        data = await api.get(f"/habits/{habit_id}/history", params={
            "telegram_id": user_id,
            "username": call.from_user.username,
            "first_name": call.from_user.first_name,
            "last_name": call.from_user.last_name,
            "photo_url": photo_url,
            "period": "week"
        })
        history = data.get("history", [])
        habit = data.get("habit", {})
        
        name = habit.get("name", "Привычка")
        emoji = habit.get("emoji", "📌")
        unit = habit.get("unit", "")
        
        text = f"📊 История выполнения \"{emoji} {name}\":\n\n"
        
        if not history:
            text += "История пуста"
        else:
            for entry in history[:10]:  # Показываем последние 10 записей
                date = entry.get("date", "")
                completed = entry.get("completed", False)
                amount = entry.get("amount", 0)
                
                if completed:
                    if unit and amount > 0:
                        text += f"{date} ✅ {amount} {unit}\n"
                    else:
                        text += f"{date} ✅\n"
                else:
                    text += f"{date} ❌ не выполнено\n"
        
        await call.message.edit_text(text, reply_markup=get_stats_period_keyboard(habit_id))
        await call.answer()
    except Exception as e:
        await call.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(lambda c: c.data and c.data.startswith("stats_period:"))
async def change_stats_period(call: types.CallbackQuery):
    if not call.data or not call.from_user:
        return await call.answer("❌ Ошибка", show_alert=True)
    
    parts = call.data.split(":")
    habit_id = parts[1]
    period = parts[2]
    user_id = call.from_user.id

    try:
        photo_url = await get_user_photo_url(call.bot, user_id)
        data = await api.get(f"/habits/{habit_id}/stats", params={
            "telegram_id": user_id,
            "username": call.from_user.username,
            "first_name": call.from_user.first_name,
            "last_name": call.from_user.last_name,
            "photo_url": photo_url,
            "period": period
        })
        stats = data.get("stats", {})
        habit = data.get("habit", {})
        
        name = habit.get("name", "Привычка")
        emoji = habit.get("emoji", "📌")
        completed = stats.get("completed", 0)
        total = stats.get("total", 7)
        streak = stats.get("current_streak", 0)
        best_streak = stats.get("best_streak", 0)
        last_completed = stats.get("last_completed")
        avg_frequency = stats.get("avg_frequency", 0)
        
        percentage = int((completed / total * 100)) if total > 0 else 0
        
        text = f"📈 Привычка: {emoji} {name}\n"
        text += f"Выполнено: {completed} из {total} ({percentage}%)\n"
        text += f"Серия: {streak} дней 🔥\n"
        text += f"Лучшая серия: {best_streak} дней (макс.)\n"
        
        if last_completed:
            text += f"Последний раз: {last_completed}\n"
        
        if avg_frequency > 0:
            text += f"Средняя частота: {avg_frequency:.1f} раза/неделю"
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📊 Детальная история", callback_data=f"stats_detail:{habit_id}")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data=f"habit_select:{habit_id}")],
                [InlineKeyboardButton(text="📅 Главное меню", callback_data="main_menu")]
            ]
        )
        
        await call.message.edit_text(text, reply_markup=keyboard)
        await call.answer()
    except Exception as e:
        await call.answer(f"❌ Ошибка: {e}", show_alert=True)


