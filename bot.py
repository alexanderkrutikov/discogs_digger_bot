import logging
import re
import json
import requests
import time
from requests_oauthlib import OAuth1Session
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ConversationHandler

# Ваши данные для Discogs API
consumer_key = "MppNoSwunrRGkCJoVOxK"
consumer_secret = "qbtwSvSvQrCnnkvuTlBCPyiPiqLAiGYL"
callback_uri = "oob"
user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
token_file = "discogs_token.json"  # Файл для хранения токена

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

# Извлечение ID артиста из URL
def extract_artist_id_from_url(url):
    match = re.search(r"/artist/(\d+)", url)
    if match:
        return match.group(1)
    return None

# Извлечение ID лейбла из URL
def extract_label_id_from_url(url):
    match = re.search(r"/label/(\d+)", url)
    if match:
        return match.group(1)
    return None

# Получение имени артиста
def get_artist_name(artist_id, oauth_session):
    try:
        api_url = f"https://api.discogs.com/artists/{artist_id}"
        headers = {"User-Agent": user_agent}
        response = oauth_session.get(api_url, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data.get("name")
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при получении имени артиста: {e}")
        return None

# Получение имени лейбла
def get_label_name(label_id, oauth_session):
    try:
        api_url = f"https://api.discogs.com/labels/{label_id}"
        headers = {"User-Agent": user_agent}
        response = oauth_session.get(api_url, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data.get("name")
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при получении имени лейбла: {e}")
        return None

# Получение ID релизов артиста
def get_artist_release_ids(artist_id, oauth_session):
    release_ids = []
    page_num = 1
    per_page = 100

    while True:
        try:
            search_url = f"https://api.discogs.com/database/search?artist_id={artist_id}&type=release&page={page_num}&per_page={per_page}"
            headers = {"User-Agent": user_agent}
            response = oauth_session.get(search_url, headers=headers)
            response.raise_for_status()
            data = response.json()

            if page_num > data['pagination']['pages']:
                break

            if not data['results']:
                break

            for release in data['results']:
                release_ids.append(release['id'])

            page_num += 1
            time.sleep(2)  # Задержка между запросами

        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при получении релизов артиста: {e}")
            break

    return release_ids

# Получение ID релизов лейбла
def get_label_release_ids(label_id, oauth_session):
    release_ids = []
    page_num = 1
    per_page = 100

    while True:
        try:
            api_url = f"https://api.discogs.com/labels/{label_id}/releases?page={page_num}&per_page={per_page}"
            headers = {"User-Agent": user_agent}
            response = oauth_session.get(api_url, headers=headers)
            response.raise_for_status()
            data = response.json()

            if page_num > data['pagination']['pages']:
                break

            if not data['releases']:
                break

            for release in data['releases']:
                release_ids.append(release['id'])

            page_num += 1
            time.sleep(2)  # Задержка между запросами

        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при получении релизов лейбла: {e}")
            break

    return release_ids

# Получение YouTube-ссылок из релиза
def get_youtube_links_from_release(release_id, oauth_session):
    youtube_links = []
    api_url = f"https://api.discogs.com/releases/{release_id}"
    headers = {"User-Agent": user_agent}

    try:
        response = oauth_session.get(api_url, headers=headers)
        response.raise_for_status()
        data = response.json()

        if 'videos' in data:
            for video in data['videos']:
                youtube_links.append(video['uri'])

    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при получении YouTube-ссылок: {e}")

    return youtube_links

# Обработчик команды /start
async def start(update: Update, context):
    await update.message.reply_text(
        "Чтобы начать поиск YouTube-ссылок на сайте Discogs, отправьте ссылки на страницы артистов или лейблов, каждая с новой строки."
    )
    return 1

# Обработчик получения ссылок
async def get_links(update: Update, context):
    links = update.message.text.split("\n")
    oauth_session = get_oauth_session()

    if not oauth_session:
        await update.message.reply_text("Ошибка: не удалось авторизоваться в Discogs.")
        return ConversationHandler.END

    results = {}
    for link in links:
        link = link.strip()
        if not link:
            continue

        # Определяем тип ссылки (артист или лейбл)
        artist_id = extract_artist_id_from_url(link)
        label_id = extract_label_id_from_url(link)

        if artist_id:
            # Обработка артиста
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

            if youtube_links:  # Проверка на наличие ссылок
                with open(filename, "w") as f:
                    f.write("\n".join(set(youtube_links)))
                results[link] = {"name": artist_name, "file": filename, "count": len(set(youtube_links))} # Добавляем количество ссылок
            else:
                results[link] = {"name": artist_name, "message": "Не найдено YouTube ссылок"}

        elif label_id:
            # Обработка лейбла
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

            if youtube_links: # Проверка на наличие ссылок
                with open(filename, "w") as f:
                    f.write("\n".join(set(youtube_links)))
                results[link] = {"name": label_name, "file": filename, "count": len(set(youtube_links))} # Добавляем количество ссылок
            else:
                results[link] = {"name": label_name, "message": "Не найдено YouTube ссылок"}

        else:
            results[link] = {"error": "Не удалось определить тип ссылки"}

    # Отправка файлов пользователю
    for link, data in results.items():
        if "error" in data:
            await update.message.reply_text(f"Ошибка обработки ссылки {link}: {data['error']}")
        elif "message" in data:
            await update.message.reply_text(f"Для {link} ({data['name']}): {data['message']}")
        else:
            count = data['count']
            message = f"Найдено {count} ссыл{'ок' if count % 10 == 0 or 5 <= count % 10 <= 9 or 11 <= count % 100 <= 14 else 'ка' if count % 10 == 1 else 'ки'}"
            with open(data["file"], "rb") as f:
                await update.message.reply_document(f, caption=f"{message} для {data['name']}")

    await update.message.reply_text("Поиск завершён. Чтобы начать новый поиск, нажмите /start.")
    return ConversationHandler.END

# Основная функция
def main():
    application = ApplicationBuilder().token("7841159840:AAGOyN5tacI6HvRtwA2_UlL8H7htnDY2Cvc").build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            1: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_links)],
        },
        fallbacks=[],
    )

    application.add_handler(conv_handler)
    application.run_polling()

if __name__ == "__main__":
    main()
