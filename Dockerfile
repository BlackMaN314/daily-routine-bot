FROM python:3.11-slim

WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Создание пользователя для запуска приложения
RUN useradd -m -u 1000 botuser

# Копирование файлов зависимостей
COPY requirements.txt .

# Установка Python зависимостей
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода приложения
COPY --chown=botuser:botuser . .

# Создание директории для данных
RUN mkdir -p /app/data && chown -R botuser:botuser /app/data

# Переключение на пользователя
USER botuser

# Команда запуска
CMD ["python", "bot.py"]

