from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from keyboards.main_menu import main_menu

router = Router()

@router.message(lambda m: m.text == "🏠 Главное меню")
async def show_main_menu(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("🏠 Главное меню", reply_markup=main_menu())

@router.callback_query(lambda c: c.data == "main_menu")
async def back_to_main_menu_callback(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.answer()
    if call.message:
        await call.message.answer("🏠 Главное меню", reply_markup=main_menu())
