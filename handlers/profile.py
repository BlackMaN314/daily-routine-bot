from aiogram import Router, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from services.api import api
from keyboards.main_menu import main_menu

router = Router()


@router.message(lambda m: m.text == "👤 Личный кабинет")
async def show_profile(message: types.Message):
    if not message.from_user:
        return await message.answer("❌ Не удалось определить пользователя")

    user_id = message.from_user.id

    try:
        data = await api.get("/telegram/auth-link", params={"telegram_id": user_id})
        web_url = data.get("url", "https://daily-routine.ru/")
        
        await message.answer(
            "👤 Личный кабинет\n\n"
            "Перенаправляет на веб-версию в личный кабинет",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🌐 Открыть веб-версию", url=web_url)],
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")],
                    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
                ]
            )
        )
    except Exception as e:
        await message.answer(
            f"❌ Не удалось получить ссылку на веб-версию.\n"
            f"Попробуй позже или обратись в поддержку.",
            reply_markup=main_menu()
        )

