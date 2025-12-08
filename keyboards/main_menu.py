from aiogram.utils.keyboard import ReplyKeyboardBuilder

def main_menu():
    """Создать клавиатуру главного меню"""
    kb = ReplyKeyboardBuilder()
    kb.button(text="📅 Привычки")
    kb.button(text="⚙️ Настройки")
    kb.button(text="👤 Личный кабинет")
    kb.adjust(2, 1)
    return kb.as_markup(resize_keyboard=True)
