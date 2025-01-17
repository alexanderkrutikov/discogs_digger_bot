import logging
import os
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Ваш API-ключ DeepSeek и токен Telegram-бота
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"  # Пример URL API

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# Функция для отправки запроса к API DeepSeek
async def get_deepseek_response(prompt):
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "deepseek-chat",  # Укажите модель
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 150
    }
    try:
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=data)
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        else:
            return f"Ошибка API: {response.status_code}, {response.text}"
    except Exception as e:
        return f"Ошибка при запросе к API: {str(e)}"

# Обработчик команды /start
async def start(update: Update, context):
    await update.message.reply_text("Привет! Я бот, использующий DeepSeek API. Напиши что-нибудь!")

# Обработчик текстовых сообщений
async def handle_message(update: Update, context):
    user_message = update.message.text
    deepseek_response = await get_deepseek_response(user_message)
    await update.message.reply_text(deepseek_response)

# Основная функция
if __name__ == "__main__":
    # Создаем приложение для бота
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Регистрируем обработчики команд и сообщений
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Запускаем бота
    logging.info("Бот запущен...")
    application.run_polling()