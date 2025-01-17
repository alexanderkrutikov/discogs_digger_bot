import logging
import os
import re
import json
import requests
from requests_oauthlib import OAuth1Session
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ConversationHandler

# Ваши данные для Discogs API
consumer_key = "MppNoSwunrRGkCJoVOxK"
consumer_secret = "qbtwSvSvQrCnnkvuTlBCPyiPiqLAiGYL"
callback_uri = "oob"
user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
token_file = "discogs_token.json"  # Файл для хранения токена

# Состояния для ConversationHandler
CHOOSING, GET_LINKS = range(2)

# Логирование
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Загрузка токена из файла
def load_token():
    try:
        with open(token_file, "r") as f:
            token_data = json.load(f)
            return token_data["access_token"], token_data["access_token_secret"]
    except FileNotFoundError:
        return None, None

# Сохранение токена в файл
def save_token(access_token, access_token_secret):
    with open(token_file, "w") as f:
        json.dump({"access_token": access_token, "access_token_secret": access_token_secret}, f)

# Получение OAuth-сессии
def get_oauth_session():
    access_token, access_token_secret = load_token()
    if access_token and access_token_secret:
        return OAuth1Session(
            consumer_key,
            client_secret=consumer_secret,
            resource_owner_key=access_token,
            resource_owner_secret=access_token_secret,
        )
    else:
        return None

# Обработчик команды /start
async def start(update: Update, context):
    reply_keyboard = [["По артистам", "По лейблам"]]
    await update.message.reply_text(
        "Выберите, по чему искать ссылки на YouTube:",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True),
    )
    return CHOOSING

# Обработчик выбора типа поиска
async def choose_search_type(update: Update, context):
    user_choice = update.message.text
    context.user_data["search_type"] = user_choice
    await update.message.reply_text("Введите ссылки на страницы артистов или лейблов (каждая ссылка с новой строки):")
    return GET_LINKS

# Обработчик получения ссылок
async def get_links(update: Update, context):
    links = update.message.text.split("\n")
    search_type = context.user_data.get("search_type")
    oauth_session = get_oauth_session()

    if not oauth_session:
        await update.message.reply_text("Ошибка: не удалось авторизоваться в Discogs.")
        return ConversationHandler.END

    results = {}
    for link in links:
        link = link.strip()
        if not link:
            continue

        if search_type == "По артистам":
            artist_id = extract_artist_id_from_url(link)
            if not artist_id:
                results[link] = {"error": "Не удалось извлечь ID артиста"}
                continue

            artist_name = get_artist_name(artist_id, oauth_session)
            if not artist_name:
                results[link] = {"error": "Не удалось получить имя артиста"}
                continue

            filename = f"{artist_name}.txt"
            release_ids = get_artist_release_ids(artist_id, oauth_session)
            youtube_links = []
            for release_id in release_ids:
                youtube_links.extend(get_youtube_links_from_release(release_id, oauth_session))
                time.sleep(1)  # Задержка между запросами

            with open(filename, "w") as f:
                f.write("\n".join(set(youtube_links)))

            results[link] = {"name": artist_name, "file": filename}

        elif search_type == "По лейблам":
            label_id = extract_label_id_from_url(link)
            if not label_id:
                results[link] = {"error": "Не удалось извлечь ID лейбла"}
                continue

            label_name = get_label_name(label_id, oauth_session)
            if not label_name:
                results[link] = {"error": "Не удалось получить название лейбла"}
                continue

            filename = f"{label_name}.txt"
            release_ids = get_label_release_ids(label_id, oauth_session)
            youtube_links = []
            for release_id in release_ids:
                youtube_links.extend(get_youtube_links_from_release(release_id, oauth_session))
                time.sleep(1)  # Задержка между запросами

            with open(filename, "w") as f:
                f.write("\n".join(set(youtube_links)))

            results[link] = {"name": label_name, "file": filename}

    # Отправка файлов пользователю
    for link, data in results.items():
        if "error" in data:
            await update.message.reply_text(f"Ошибка обработки ссылки {link}: {data['error']}")
        else:
            with open(data["file"], "rb") as f:
                await update.message.reply_document(f, caption=f"Ссылки для {data['name']}")

    return ConversationHandler.END

# Обработчик отмены
async def cancel(update: Update, context):
    await update.message.reply_text("Поиск отменён.")
    return ConversationHandler.END

# Основная функция
def main():
    application = ApplicationBuilder().token("7711337892:AAEm15FsePjsgikQOBCi63GIi50jmMk8fQ8").build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_search_type)],
            GET_LINKS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_links)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    application.run_polling()

if __name__ == "__main__":
    main()