from aiogram import Router, types, Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from services.api import api
from keyboards.main_menu import main_menu
from handlers.start import get_user_photo_url

router = Router()


def get_morning_notification_keyboard(habits: list):
    keyboard = []
    if habits:
        keyboard.append([InlineKeyboardButton(text="✅ Отметить все выполненными", callback_data="morning_complete_all")])
    keyboard.append([InlineKeyboardButton(text="📋 Открыть список", callback_data="morning_open_list")])
    keyboard.append([InlineKeyboardButton(text="🔕 Отключить напоминания", callback_data="morning_disable")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


async def send_morning_notification(bot: Bot, user_id: int):
    try:
        photo_url = await get_user_photo_url(bot, user_id)
        data = await api.get("/habits/today", params={
            "telegram_id": user_id,
            "photo_url": photo_url
        })
        habits = data.get("habits", [])
        
        if not habits:
            return
        
        text = "🌞 Доброе утро!\n"
        text += f"Сегодня у тебя {len(habits)} привычек:\n\n"
        
        for habit in habits:
            emoji = habit.get("emoji", "📌")
            name = habit.get("name", "Неизвестно")
            text += f"{emoji} {name}\n"
        
        await bot.send_message(
            user_id,
            text,
            reply_markup=get_morning_notification_keyboard(habits)
        )
    except Exception:
        pass  # Игнорируем ошибки при отправке уведомлений


@router.callback_query(lambda c: c.data == "morning_complete_all")
async def complete_all_morning(call: types.CallbackQuery):
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
        
        completed_habits = []
        for habit in habits:
            habit_id = habit.get("id")
            try:
                result = await api.post("/habits/complete", {
                    "telegram_id": user_id,
                    "username": call.from_user.username,
                    "first_name": call.from_user.first_name,
                    "last_name": call.from_user.last_name,
                    "photo_url": photo_url,
                    "habit_id": habit_id
                })
                completed_habits.append({
                    "name": habit.get("name", "Привычка"),
                    "streak": result.get("streak", 0)
                })
            except Exception:
                pass
        
        if completed_habits:
            text = "🔥 Отлично! Все привычки отмечены выполненными!\n\n"
            for habit in completed_habits:
                text += f"✅ {habit['name']} — выполнено\n"
            
            max_streak = max([h.get("streak", 0) for h in completed_habits], default=0)
            if max_streak > 0:
                text += f"\nТвоя серия продолжается! 🔥"
            
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔄 Обновить список", callback_data="back_today")],
                    [InlineKeyboardButton(text="📅 Главное меню", callback_data="main_menu")]
                ]
            )
            
            await call.message.edit_text(text, reply_markup=keyboard)
        else:
            await call.answer("❌ Не удалось отметить привычки", show_alert=True)
        
        await call.answer()
    except Exception as e:
        await call.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(lambda c: c.data == "morning_open_list")
async def open_list_morning(call: types.CallbackQuery):
    await call.answer()
    if call.message and call.from_user:
        from handlers.habits_today import habits_today
        message = call.message
        message.text = "📅 Привычки на сегодня"
        await habits_today(message)


@router.callback_query(lambda c: c.data == "morning_disable")
async def disable_morning_notifications(call: types.CallbackQuery):
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
            "🔕 Утренние напоминания отключены",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")]]
            )
        )
        await call.answer()
    except Exception as e:
        await call.answer(f"❌ Ошибка: {e}", show_alert=True)

