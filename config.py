import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
BACKEND_USER_ID = os.getenv("BACKEND_USER_ID")
BACKEND_ACCESS_TOKEN = os.getenv("BACKEND_ACCESS_TOKEN")
BACKEND_REFRESH_TOKEN = os.getenv("BACKEND_REFRESH_TOKEN")
WEB_APP_URL = os.getenv("WEB_APP_URL", "https://daily-routine.ru")
NOTIFICATION_SERVER_HOST = os.getenv("NOTIFICATION_SERVER_HOST", "0.0.0.0")
NOTIFICATION_SERVER_PORT = int(os.getenv("NOTIFICATION_SERVER_PORT", "8080"))