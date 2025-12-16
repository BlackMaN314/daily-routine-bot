import logging
from aiohttp import web
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from typing import Optional

logger = logging.getLogger(__name__)


class NotificationServer:
    def __init__(self, bot: Bot, host: str = "0.0.0.0", port: int = 8080):
        self.bot = bot
        self.host = host
        self.port = port
        self.app = web.Application()
        self._setup_routes()
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None
    
    def _setup_routes(self):
        self.app.router.add_post("/notify", self.handle_notify)
        self.app.router.add_get("/health", self.handle_health)
    
    async def handle_health(self, request: web.Request) -> web.Response:
        return web.json_response({"status": "ok", "service": "telegram-bot-notifications"})
    
    async def handle_notify(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
            
            telegram_id = data.get("telegram_id")
            message = data.get("message")
            
            if telegram_id is None:
                return web.json_response(
                    {"error": "telegram_id is required"},
                    status=400
                )
            
            try:
                telegram_id = int(telegram_id)
            except (ValueError, TypeError):
                return web.json_response(
                    {"error": "telegram_id must be a valid integer"},
                    status=400
                )
            
            if not message or not isinstance(message, str) or not message.strip():
                return web.json_response(
                    {"error": "message is required and must be a non-empty string"},
                    status=400
                )
            
            reply_markup = None
            keyboard_data = data.get("keyboard")
            if keyboard_data:
                reply_markup = self._parse_keyboard(keyboard_data)
            
            try:
                sent_message = await self.bot.send_message(
                    chat_id=telegram_id,
                    text=message,
                    reply_markup=reply_markup
                )
                
                return web.json_response({
                    "success": True,
                    "message_id": sent_message.message_id,
                    "telegram_id": telegram_id
                })
            
            except TelegramForbiddenError:
                pass
                return web.json_response(
                    {
                        "error": "User blocked the bot",
                        "telegram_id": telegram_id
                    },
                    status=403
                )
            except TelegramBadRequest as e:
                logger.error(f"Ошибка Telegram API при отправке уведомления пользователю {telegram_id}: {e}")
                return web.json_response(
                    {
                        "error": f"Telegram API error: {str(e)}",
                        "telegram_id": telegram_id
                    },
                    status=400
                )
            except Exception as e:
                logger.error(f"Ошибка при отправке уведомления пользователю {telegram_id}: {e}", exc_info=True)
                return web.json_response(
                    {
                        "error": f"Failed to send message: {str(e)}",
                        "telegram_id": telegram_id
                    },
                    status=500
                )
        
        except Exception as e:
            logger.error(f"Ошибка при обработке запроса на уведомление: {e}")
            return web.json_response(
                {"error": f"Invalid request: {str(e)}"},
                status=400
            )
    
    def _parse_keyboard(self, keyboard_data: list) -> Optional[InlineKeyboardMarkup]:
        if not keyboard_data:
            return None
        
        inline_keyboard = []
        
        for row in keyboard_data:
            if not isinstance(row, list):
                continue
            
            button_row = []
            for button_data in row:
                if not isinstance(button_data, dict):
                    continue
                
                text = button_data.get("text")
                if not text:
                    continue
                
                if "url" in button_data:
                    button = InlineKeyboardButton(text=text, url=button_data["url"])
                elif "callback_data" in button_data:
                    button = InlineKeyboardButton(text=text, callback_data=button_data["callback_data"])
                else:
                    continue
                
                button_row.append(button)
            
            if button_row:
                inline_keyboard.append(button_row)
        
        if not inline_keyboard:
            return None
        
        return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
    
    async def start(self):
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, self.host, self.port)
        await self.site.start()
    
    async def stop(self):
        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()

