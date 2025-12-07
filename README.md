# DailyRoutine Telegram Bot

Telegram-бот для отслеживания ежедневных привычек.

## Требования

- Python 3.8+
- Telegram Bot Token
- Backend API

## Установка

```bash
git clone <repository-url>
cd daily-routine-bot
python -m venv venv
source venv/bin/activate  # или venv\Scripts\activate на Windows
pip install -r requirements.txt
```

## Конфигурация

Создайте файл `.env`:

```env
BOT_TOKEN=your_telegram_bot_token_here
BACKEND_URL=http://localhost:8000
WEB_APP_URL=https://daily-routine.ru
NOTIFICATION_SERVER_HOST=0.0.0.0
NOTIFICATION_SERVER_PORT=8080
```

## Запуск

```bash
python bot.py
```

База данных SQLite создается автоматически в `data/tokens.db`.

## Деплой

### Docker

```bash
docker-compose up -d
```

### Systemd

```bash
sudo cp daily-routine-bot.service /etc/systemd/system/
sudo systemctl enable daily-routine-bot
sudo systemctl start daily-routine-bot
```

## Структура проекта

```
daily-routine-bot/
├── bot.py                 # Главный файл
├── config.py              # Конфигурация
├── requirements.txt        # Зависимости
├── handlers/              # Обработчики
├── services/              # Сервисы (API, токены, уведомления)
└── keyboards/             # Клавиатуры
```
