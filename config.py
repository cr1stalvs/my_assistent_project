from dotenv import load_dotenv, find_dotenv

from os import getenv

load_dotenv(find_dotenv())  # подгружает информацию из .env
# При помощи команды find_dotenv (сразу из каталога проекта)

FOLDER_ID = getenv("FOLDER_ID")  # ID папки в Yandex Cloud.

IAM_TOKEN = getenv('IAM_TOKEN')  # IAM токен Yandex Cloud.

TOKEN = getenv("TOKEN")  # token tg-bota

ADMINS_IDS = getenv("ADMINS_IDS")  # id admina

TOKENIZE_URL = getenv("TOKENIZE_URL")

GPT_MODEL = getenv("GPT_MODEL")

GPT_URL = getenv("GPT_URL")


MAX_USERS = 3  # максимальное кол-во пользователей

MAX_GPT_TOKENS = 120  # максимальное кол-во токенов в ответе GPT

COUNT_LAST_MSG = 4  # кол-во последних сообщений из диалога

# лимиты для пользователя

MAX_USER_STT_BLOCKS = 10  # 10 аудиоблоков

MAX_USER_TTS_SYMBOLS = 5_000  # 5 000 символов

MAX_USER_GPT_TOKENS = 2_000  # 2 000 токенов

LOGS = 'creds/logs.txt'  # файл для логов

DB_FILE = 'messages.db'  # файл для базы данных

SYSTEM_PROMPT = [{'role': 'system', 'text': 'Ты веселый собеседник. Общайся с пользователем на "ты" и используй юмор. '
                                            'Поддерживай диалог. Не объясняй пользователю, что ты умеешь и можешь. '
                                            'Изображай человека'}]  # список с системным промтом

