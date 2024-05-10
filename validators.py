import logging  # модуль для сбора логов

import math  # математический модуль для округления

# подтягиваем инфу из config-файла
from config import LOGS, MAX_USERS, MAX_USER_GPT_TOKENS, MAX_USER_TTS_SYMBOLS, MAX_USER_STT_BLOCKS, ADMINS_IDS

# подтягиваем функции для работы с БД
from db import count_users, count_all_limits

# подтягиваем функцию для подсчета токенов в списке сообщений
from yandex_gpt import count_gpt_tokens



# Настраиваем запись логов в файл
logging.basicConfig(filename=LOGS, level=logging.DEBUG,
                    format="%(asctime)s FILE: %(filename)s IN: %(funcName)s MESSAGE: %(message)s", filemode="a")


# Функция для получения количества уникальных пользователей,
# кроме самого пользователя
def check_number_of_users(user_id):
    count = count_users(user_id)
    if count is None:
        return None, "Ошибка при работе с БД"
    if count > MAX_USERS:
        return None, "Превышено максимальное количество пользователей"
    return True, ""

# Функция для проверки, не превысил ли пользователь лимиты на общение с GPT
def is_gpt_token_limit(messages, total_spent_tokens, user_id):
    all_tokens = count_gpt_tokens(messages) + total_spent_tokens
    if all_tokens > MAX_USER_GPT_TOKENS and str(user_id) not in ADMINS_IDS:
        return None, f"Превышен общий лимит GPT-токенов {MAX_USER_GPT_TOKENS}"
    return all_tokens, ""

# Эта функция проверяет,
# превышено ли количество доступных пользователю токенов GPT.
def is_stt_block_limit(user_id, duration):
# проверяем, не превысил ли пользователь лимиты на преобразование текста в аудио
    audio_blocks = math.ceil(duration / 15)
    all_blocks = count_all_limits(user_id, 'stt_blocks') + audio_blocks

    if duration >= 30:
        response = "SpeechKit STT работает с голосовыми сообщениями меньше 30 секунд"
        return None, response

    if all_blocks >= MAX_USER_STT_BLOCKS and str(user_id) not in ADMINS_IDS:
        response = (f"Превышен общий лимит SpeechKit STT {MAX_USER_STT_BLOCKS}. Использовано {all_blocks} блоков. "
                    f"Доступно: "f"{MAX_USER_STT_BLOCKS - all_blocks}")
        return None, response

    return audio_blocks, None


# Эта функция проверяет,
# превышено ли количество доступных пользователю символов TTS.
def is_tts_symbol_limit(user_id, text):
    text_symbols = len(text)

    all_symbols = count_all_limits(user_id, 'tts_symbols') + text_symbols

    if all_symbols >= MAX_USER_TTS_SYMBOLS and str(user_id) not in ADMINS_IDS:
        msg = (f"Превышен общий лимит SpeechKit TTS {MAX_USER_TTS_SYMBOLS}. Использовано: {all_symbols} символов. "
               f"Доступно: {MAX_USER_TTS_SYMBOLS - all_symbols}")
        return None, msg

    return text_symbols, None