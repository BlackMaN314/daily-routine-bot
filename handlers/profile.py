from aiogram import Router, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from services.api import api
from keyboards.main_menu import main_menu
from utils.helpers import get_user_params, format_error_message

router = Router()


@router.message(lambda m: m.text == "👤 Личный кабинет")
async def show_profile(message: types.Message):
    if not message.from_user:
        return await message.answer("❌ Не удалось определить пользователя")

    try:
        params = await get_user_params(message.from_user, message.bot)
        data = await api.get("/telegram/auth-link", params=params)
        web_url = data.get("url", "https://daily-routine.ru/")
        
        await message.answer(
            "👤 <b>Личный кабинет</b>\n\n"
            "🌐 Открой веб-версию для полного управления привычками",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🌐 Открыть веб-версию", url=web_url)]
                ]
            ),
            parse_mode="HTML"
        )
    except Exception as e:
        await message.answer(
            format_error_message(e),
            reply_markup=main_menu()
        )

