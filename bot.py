import telebot
from telebot import types
from telebot.types import Message

import logging  # модуль для сбора логов
from validators import check_number_of_users, is_gpt_token_limit, is_stt_block_limit, is_tts_symbol_limit  # модуль для валидации
from yandex_gpt import ask_gpt  # модуль для работы с GPT
from speechkit import speech_to_text, text_to_speech  # модуль для работы с STT
from config import TOKEN, LOGS, COUNT_LAST_MSG, ADMINS_IDS # подтягиваем инфу из config-файл
from db import create_database, add_message, select_n_last_messages # подтягиваем функции из database файла
# from creds import get_bot_token  # модуль для получения bot_token

# bot = telebot.TeleBot(get_bot_token())  # создаём объект бота
bot = telebot.TeleBot(TOKEN) # создаем бота

# Настраиваем запись логов в файл
logging.basicConfig(filename=LOGS, level=logging.DEBUG,
                    format="%(asctime)s FILE: %(filename)s IN: %(funcName)s MESSAGE: %(message)s", filemode="a")


# Обработчик команды /start
@bot.message_handler(commands=['start'])
def start(message: Message):
    bot.send_message(message.from_user.id, "Приветствую, мой верный подданный! Доложи мне о своих мыслях голосом или текстом, и я, твое величество, соизволю ответить. Но будь готов к шуткам и иронии в свой адрес, ибо таково мое царское призвание!")


# Обработчик команды /help
@bot.message_handler(commands=['help'])
def help(message: Message):
    bot.send_message(message.from_user.id,
                     "*Доступные команды:*\n"
                     "- /start: Чтобы приступить к общению, отправь мне голосовое сообщение или текст\n"
                     "- /feedback: Оставить отзыв\n")



# Обработчик команды /feedback
@bot.message_handler(commands=['feedback'])
def feedback_handler(msg: Message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1, one_time_keyboard=True)

    btn3 = types.KeyboardButton("Неудовлетворительный ответ от нейросети")
    btn2 = types.KeyboardButton("Не работают команды")
    btn1 = types.KeyboardButton('Все отлично,мне понравилось!')
    markup.add(btn1, btn2, btn3)
    bot.send_message(msg.chat.id, 'Оставьте отзыв, если вам не сложно!\n'
                                  '(можете просто написать сообщение с отзывом\n'
                                  'или воспользоваться вариантами под строкой ввода)'.format(msg.from_user,
                                                                                             bot.get_me()),
                     reply_markup=markup,
                     parse_mode='html')

    bot.register_next_step_handler(msg, feedback)


# Функции для хранения отзывов в текстовом формате.
def feedback(msg: Message):
    with open('creds/feedback.txt', 'a', encoding='utf-8') as f: # открывает и записывает строку в файл с информацией
        # об отправившем отзыв пользователе и самим отзывом.
        f.write(f'{msg.from_user.first_name}({msg.from_user.id}) оставил отзыв - "{msg.text}"\n')  # формат записи
        bot.send_message(msg.chat.id, 'Спасибо за отзыв!')  # Отправляет сообщение в чат, где был оставлен отзыв


# Обработчик команды /debug - отправляем файл с логами
@bot.message_handler(commands=['debug'])
def debug(message: Message):
    if str(message.from_user.id) in ADMINS_IDS:
        try:
            with open(LOGS, "rb") as f:
                bot.send_document(message.chat.id, f)
        except telebot.apihelper.ApiTelegramException as e:
            bot.send_message(message.chat.id, 'Не получилось отправить файл с логами. Попробуйте позже.')
            logging.error(e)
    else:
        bot.send_message(message.from_user.id, 'У вас недостаточно прав')


# Декаратор для обрабатки текстовых сообщений,полученных ботом
@bot.message_handler(content_types=['text'])
def handle_text(message):
    """Обработчик текстовых сообщений."""

    try:
        user_id = message.from_user.id

        # ВАЛИДАЦИЯ: проверяем, есть ли место для ещё одного пользователя (если пользователь новый)
        status_check_users, error_message = check_number_of_users(user_id)
        if not status_check_users:
            bot.send_message(user_id, error_message)  # мест нет =(
            return

        # БД: добавляем сообщение пользователя и его роль в базу данных
        full_user_message = [message.text, 'user', 0, 0, 0]
        add_message(user_id=user_id, full_message=full_user_message)

        # ВАЛИДАЦИЯ: считаем количество доступных пользователю GPT-токенов
        # получаем последние 4 (COUNT_LAST_MSG) сообщения и количество уже потраченных токенов
        last_messages, total_spent_tokens = select_n_last_messages(user_id, COUNT_LAST_MSG)
        # получаем сумму уже потраченных токенов + токенов в новом сообщении и оставшиеся лимиты пользователя
        total_gpt_tokens, error_message = is_gpt_token_limit(last_messages, total_spent_tokens)
        if error_message:
            # если что-то пошло не так — уведомляем пользователя и прекращаем выполнение функции
            bot.send_message(user_id, error_message)
            return

        # GPT: отправляем запрос к GPT
        status_gpt, answer_gpt, tokens_in_answer = ask_gpt(last_messages)
        # GPT: обрабатываем ответ от GPT
        if not status_gpt:
            # если что-то пошло не так — уведомляем пользователя и прекращаем выполнение функции
            bot.send_message(user_id, answer_gpt)
            return
        # сумма всех потраченных токенов + токены в ответе GPT
        total_gpt_tokens += tokens_in_answer

        # БД: добавляем ответ GPT и потраченные токены в базу данных
        full_gpt_message = [answer_gpt, 'assistant', total_gpt_tokens, 0, 0]
        add_message(user_id=user_id, full_message=full_gpt_message)

        bot.send_message(user_id, answer_gpt, reply_to_message_id=message.id)  # отвечаем пользователю текстом
    except Exception as e:
        logging.error(e)  # если ошибка — записываем её в логи
        bot.send_message(message.from_user.id, "Не получилось ответить. Попробуй написать другое сообщение")



# Декаратор для обработки команды распознавания речи.
@bot.message_handler(commands=['stt', 'start'])
def stt_handler(message):
    """Обработчик команды распознавания речи."""

    user_id = message.from_user.id
    # Отправляем пользователю сообщение с просьбой отправить голосовое сообщение.
    bot.send_message(user_id, 'Отправь голосовое сообщение, чтобы я его распознал!')
    # Регистрируем обработчик следующего шага, который будет вызван, когда пользователь отправит голосовое сообщение.
    bot.register_next_step_handler(message, stt)
def stt(message: Message):
    """Обработчик голосового сообщения."""

    user_id = message.from_user.id
    # Проверяем, отправил ли пользователь голосовое сообщение.
    if not message.voice:
        return

    # Проверяем, не превысил ли пользователь лимит на распознавание речи.
    success, stt_blocks = is_stt_block_limit(user_id, message.voice.duration)
    if not success:
        # Если пользователь превысил лимит, отправляем ему сообщение с соответствующей информацией.
        bot.send_message(user_id, stt_blocks)
        return

    # Получаем файл голосового сообщения.
    file_id = message.voice.file_id
    file_info = bot.get_file(file_id)
    file = bot.download_file(file_info.file_path)

    # Распознаем речь из голосового сообщения.
    status, text = speech_to_text(file)

    # Добавляем в список сообщений распознанный текст.
    add_message(user_id, [text, 'assistant', 0, 0, stt_blocks])

    # Отправляем пользователю распознанный текст.
    if status:
        bot.send_message(user_id, text, reply_to_message_id=message.id)
    else:
        bot.send_message(user_id, text)



# Декаратор для обработки команды синтеза речи.
@bot.message_handler(commands=['tts'])
def tts_handler(message):
    """Обработчик команды синтеза речи."""

    user_id = message.from_user.id
    # Отправляем пользователю сообщение с просьбой отправить текст.
    bot.send_message(user_id, 'Отправь следующим сообщеним текст, чтобы я его озвучил!')
    # Регистрируем обработчик следующего шага, который будет вызван, когда пользователь отправит текст.
    bot.register_next_step_handler(message, tts)

def tts(message: Message):
    """Обработчик текста для синтеза речи."""

    user_id = message.from_user.id
    text = message.text
    # Проверяем, отправил ли пользователь текстовое сообщение.
    if message.content_type != 'text':
        bot.send_message(user_id, 'Отправь текстовое сообщение')
        return

    # Проверяем, не превысил ли пользователь лимит на символы для синтеза речи.
    tts_symbol, error_message = is_tts_symbol_limit(user_id, text)
    if error_message and user_id not in ADMINS_IDS:
        bot.send_message(user_id, error_message)
        return

    # Синтезируем речь из текста.
    status, content = text_to_speech(text)

    # Добавляем в список сообщений синтезированную речь.
    add_message(user_id, [text, 'user', 0, tts_symbol, 0])

    # Отправляем пользователю синтезированную речь.
    if status:
        bot.send_voice(user_id, content)
    else:
        bot.send_message(user_id, content)



# Декоратор для обработки голосовых сообщений, полученных ботом
@bot.message_handler(content_types=['voice'])
def handle_voice(message: Message):
    """Обработчик голосовых сообщений."""

    user_id = message.from_user.id  # Идентификатор пользователя, который отправил сообщение

    try:
        # Проверка количества активных пользователей
        status_check_users, error_message = check_number_of_users(user_id)
        if not status_check_users:
            bot.send_message(user_id, error_message)
            return

        # Проверка лимита на использование STT
        stt_blocks, error_message = is_stt_block_limit(user_id, message.voice.duration)
        if error_message:
            bot.send_message(user_id, error_message)
            return

        # Скачивание и обработка голосового сообщения
        file_id = message.voice.file_id  # Идентификатор голосового файла в сообщении
        file_info = bot.get_file(file_id)  # Получение информации о файле для загрузки
        file = bot.download_file(file_info.file_path)  # Загрузка файла по указанному пути

        # Преобразование голосового сообщения в текст с помощью SpeechKit
        status_stt, stt_text = speech_to_text(file)   # Обращение к функции speech_to_text для получения текста
        if not status_stt:
            # Отправка сообщения об ошибке, если преобразование не удалось
            bot.send_message(user_id, stt_text)
            return

        # Добавление распознанного текста в список сообщений
        add_message(user_id=user_id, full_message=[stt_text, 'user', 0, 0, stt_blocks])

        # Получение списка последних сообщений
        last_messages, total_spent_tokens = select_n_last_messages(user_id, COUNT_LAST_MSG)

        # Проверка лимита на использование GPT
        total_gpt_tokens, error_message = is_gpt_token_limit(last_messages, total_spent_tokens, user_id)
        if error_message:
            bot.send_message(user_id, error_message)
            return

        # Запрос ответа от GPT
        status_gpt, answer_gpt, tokens_in_answer = ask_gpt(last_messages)  # Обращение к GPT с запросом
        if not status_gpt:
            # Отправка сообщения об ошибке, если GPT не смог сгенерировать ответ
            bot.send_message(user_id, answer_gpt)
            return
        total_gpt_tokens += tokens_in_answer

        # Проверка лимита на использование TTS
        tts_symbols, error_message = is_tts_symbol_limit(user_id, answer_gpt)

        # Добавление ответа GPT в список сообщений
        add_message(user_id=user_id, full_message=[answer_gpt, 'assistant', total_gpt_tokens, tts_symbols, 0])

        if error_message:
            bot.send_message(user_id, error_message)
            return

        # Преобразование текстового ответа от GPT в голосовое сообщение
        status_tts, voice_response = text_to_speech(answer_gpt)   # Обращение к функции text_to_speech для получения аудио

        # Отправка голосового сообщения или текста в зависимости от результата синтеза речи
        if status_tts:
            # Отправка текстового ответа GPT, если преобразование в аудио не удалось
            bot.send_voice(user_id, voice_response, reply_to_message_id=message.id)
        else:
            # Отправка голосового сообщения, если преобразование в аудио прошло успешно
            bot.send_message(user_id, answer_gpt, reply_to_message_id=message.id)

    except Exception as e:
        # Логирование ошибки
        logging.error(e)
        # Уведомление пользователя о непредвиденной ошибке
        bot.send_message(user_id, "Не получилось ответить. Попробуй записать другое сообщение")



# Запуск всего этого добра
if __name__ == '__main__':
    logging.info('programm start')
    create_database()
    bot.infinity_polling()


# bot.py — код бота
# db.py — код для работы с базой данных
# speechkit.py — код для работы со SpeechKit
# yandex_gpt.py — код для работы с YandexGPT
# validators.py — файл, в который можно вынести функции для проверки лимитов (по желанию)
# config.py — файл для хранения полезных констант проекта
# creds.py — директория для хранения данных учётной записи

# Вспомогательные файлы для добавления в репозиторий:
# requirements.txt — список зависимостей проекта
# .gitignore — список файлов, которые не нужно загружать на Гитхаб
# Readme.md — описание проекта
