from aiogram import Router, types, Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from services.api import api
from keyboards.main_menu import main_menu
from handlers.start import get_user_photo_url

router = Router()


def get_period_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📅 Сегодня", callback_data="progress_period:today")],
            [InlineKeyboardButton(text="📆 Неделя", callback_data="progress_period:week")],
            [InlineKeyboardButton(text="📈 Месяц", callback_data="progress_period:month")],
            [InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")]
        ]
    )


@router.message(lambda m: m.text == "📊 Прогресс недели")
async def week_progress(message: types.Message):
    if not message.from_user:
        return await message.answer("❌ Не удалось определить пользователя")

    user_id = message.from_user.id

    try:
        photo_url = await get_user_photo_url(message.bot, user_id)
        data = await api.get("/habits/progress", params={
            "telegram_id": user_id,
            "username": message.from_user.username,
            "first_name": message.from_user.first_name,
            "last_name": message.from_user.last_name,
            "photo_url": photo_url,
            "period": "week"
        })
        habits_progress = data.get("habits", [])
        total_progress = data.get("total", {})
        best_streak = data.get("best_streak", {})
        
        text = "📊 Прогресс за неделю:\n\n"
        
        if not habits_progress:
            text += "У тебя пока нет привычек 😔"
        else:
            for habit in habits_progress:
                emoji = habit.get("emoji", "📌")
                name = habit.get("name", "Неизвестно")
                completed = habit.get("completed", 0)
                total = habit.get("total", 7)
                text += f"{emoji} {name} — {completed} / {total}\n"
            
            text += "--------------------\n"
            total_completed = total_progress.get("completed", 0)
            total_habits = total_progress.get("total", 0)
            percentage = int((total_completed / total_habits * 100)) if total_habits > 0 else 0
            text += f"Общий прогресс: {total_completed} / {total_habits} ({percentage}%)\n"
            
            if best_streak:
                best_name = best_streak.get("name", "")
                best_days = best_streak.get("days", 0)
                if best_days > 0:
                    text += f"🔥 Лучшая серия: {best_name} ({best_days} дней)"
        
        await message.answer(text, reply_markup=get_period_keyboard())
    except Exception as e:
        await message.answer(
            f"❌ Произошла ошибка\n\n"
            f"Не удалось загрузить прогресс.\n"
            f"Попробуй еще раз.",
            reply_markup=types.ReplyKeyboardMarkup(
                keyboard=[
                    [types.KeyboardButton(text="🔄 Попробовать снова")],
                    [types.KeyboardButton(text="🔙 Главное меню")]
                ],
                resize_keyboard=True
            )
        )


@router.callback_query(lambda c: c.data and c.data.startswith("progress_period:"))
async def change_progress_period(call: types.CallbackQuery):
    if not call.data or not call.from_user:
        return await call.answer("❌ Ошибка", show_alert=True)
    
    period = call.data.split(":")[1]
    user_id = call.from_user.id
    
    period_names = {
        "today": "Сегодня",
        "week": "Неделя",
        "month": "Месяц"
    }
    period_name = period_names.get(period, "Неделя")

    try:
        photo_url = await get_user_photo_url(call.bot, user_id)
        data = await api.get("/habits/progress", params={
            "telegram_id": user_id,
            "username": call.from_user.username,
            "first_name": call.from_user.first_name,
            "last_name": call.from_user.last_name,
            "photo_url": photo_url,
            "period": period
        })
        habits_progress = data.get("habits", [])
        total_progress = data.get("total", {})
        best_streak = data.get("best_streak", {})
        
        text = f"📊 Прогресс за {period_name.lower()}:\n\n"
        
        if not habits_progress:
            text += "У тебя пока нет привычек 😔"
        else:
            for habit in habits_progress:
                emoji = habit.get("emoji", "📌")
                name = habit.get("name", "Неизвестно")
                completed = habit.get("completed", 0)
                total = habit.get("total", 7)
                text += f"{emoji} {name} — {completed} / {total}\n"
            
            text += "--------------------\n"
            total_completed = total_progress.get("completed", 0)
            total_habits = total_progress.get("total", 0)
            percentage = int((total_completed / total_habits * 100)) if total_habits > 0 else 0
            text += f"Общий прогресс: {total_completed} / {total_habits} ({percentage}%)\n"
            
            if best_streak:
                best_name = best_streak.get("name", "")
                best_days = best_streak.get("days", 0)
                if best_days > 0:
                    text += f"🔥 Лучшая серия: {best_name} ({best_days} дней)"
        
        await call.message.edit_text(text, reply_markup=get_period_keyboard())
        await call.answer()
    except Exception as e:
        await call.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.message(lambda m: m.text == "🔄 Попробовать снова")
async def retry_progress(message: types.Message):
    await week_progress(message)

