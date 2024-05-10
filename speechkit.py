import requests # модуль для отправки HTTP-запросов

import logging # модуль для сбора логов

from config import IAM_TOKEN, LOGS, FOLDER_ID  # подтягиваем инфу из config-файла

# from creds import get_creds  # модуль для получения токенов


# iam_token, folder_id = get_creds()  # получаем iam_token и folder_id из файлов

# Настраиваем запись логов в файл
logging.basicConfig(filename=LOGS, level=logging.DEBUG,
                    format="%(asctime)s FILE: %(filename)s IN: %(funcName)s MESSAGE: %(message)s", filemode="a")


# Функция text_to_speech принимает текст и отправляет запрос
# на синтез речи в Yandex Cloud API.
def text_to_speech(text):
    # Настройка заголовков запроса.
    headers = {
        'Authorization': f'Bearer {IAM_TOKEN}',
    }
    # Настройка данных, передаваемых в запросе.
    data = {
        'text': text,
        'lang': 'ru-RU',
        'voice': 'filipp',
        'folderId': FOLDER_ID
    }
    # Отправляем POST-запрос на API Yandex Cloud.
    response = requests.post(
        'https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize',
        headers=headers,
        data=data
    )
    # Обрабатываем ответ API.
    if response.status_code == 200:
        # При успешном выполнении запроса возвращаем True и содержимое ответа (аудиофайл).
        return True, response.content
    else:
        # При ошибке возвращаем False и сам ответ.
        return False, response

# Функция speech_to_text принимает аудиофайл и отправляет запрос на распознавание речи в Yandex Cloud API.
def speech_to_text(data):
    # Настройка параметров запроса.
    params = "&".join([
        "topic=general",
        f"folderId={FOLDER_ID}",
        "lang=ru-RU"
    ])

    # Настройка заголовков запроса.
    headers = {
        'Authorization': f'Bearer {IAM_TOKEN}',
    }

    # Отправляем POST-запрос на API Yandex Cloud.
    response = requests.post(
        "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize?"+params,
        headers=headers,
        data=data
    )

    # Декодируем полученный ответ.
    decoded_data = response.json()

    # Обрабатываем ответ API.
    if decoded_data.get("error_code") is None:
        # При успешном выполнении запроса возвращаем True и распознанный текст.
        logging.info('Получен ответ от нейросети')
        return True, decoded_data.get("result")

    else:
        # При ошибке возвращаем False и сообщение об ошибке.
        msg = "При запросе в SpeechKit возникла ошибка"
        logging.error(msg)
        return False, msg
