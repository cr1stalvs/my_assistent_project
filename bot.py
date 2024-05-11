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
    bot.send_message(message.from_user.id, "Приветствую, мой верный подданный!\n"
                                           "Доложи мне о своих мыслях голосом или текстом, и я, твое величество, соизволю ответить.\n"
                                           "Но будь готов к шуткам и иронии в свой адрес, ибо таково мое царское призвание!\n")


# Обработчик команды /command1
@bot.message_handler(commands=['command1'])
def start(message: Message):
    bot.send_message(message.from_user.id, "Приветствую, мой верный подданный!\n"
                                           "Доложи мне о своих мыслях голосом или текстом, и я, твое величество, соизволю ответить.\n"
                                           "Но будь готов к шуткам и иронии в свой адрес, ибо таково мое царское призвание!\n")



# Обработчик команды /help
@bot.message_handler(commands=['help'])
def help(message: Message):
    bot.send_message(message.from_user.id,
                     "Доступные команды:\n"
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


# Обработчик голосовых сообщений
@bot.message_handler(content_types=['voice'])
def handle_voice(message: Message):
    user_id = message.from_user.id
    try:
        # Проверка количества пользователей и их статуса
        status_check_users, error_message = check_number_of_users(user_id)
        if not status_check_users:
            bot.send_message(user_id, error_message)
            return

        # Проверка лимита блоков распознавания речи (Speech-to-Text)
        stt_blocks, error_message = is_stt_block_limit(user_id, message.voice.duration)
        if error_message:
            bot.send_message(user_id, error_message)
            return

        # Получение информации о голосовом сообщении и его скачивание
        file_id = message.voice.file_id
        file_info = bot.get_file(file_id)
        file = bot.download_file(file_info.file_path)

        # Преобразование речи в текст
        status_stt, stt_text = speech_to_text(file)
        if not status_stt:
            bot.send_message(user_id, stt_text)
            return

        # Сохранение распознанного текста и его атрибутов
        add_message(user_id=user_id, full_message=[stt_text, 'user', 0, 0, stt_blocks])

        # Получение последних сообщений пользователя и общего количества потраченных токенов
        last_messages, total_spent_tokens = select_n_last_messages(user_id, COUNT_LAST_MSG)

        # Проверка лимита токенов для модели GPT
        total_gpt_tokens, error_message = is_gpt_token_limit(last_messages, total_spent_tokens, user_id)
        if error_message:
            bot.send_message(user_id, error_message)
            return

        # Запрос к модели GPT для генерации ответа на основе последних сообщений пользователя
        status_gpt, answer_gpt, tokens_in_answer = ask_gpt(last_messages)
        if not status_gpt:
            bot.send_message(user_id, answer_gpt)
            return
        total_gpt_tokens += tokens_in_answer

        # Проверка лимита символов для синтеза речи (Text-to-Speech)
        tts_symbols, error_message = is_tts_symbol_limit(user_id, answer_gpt)

        # Сохранение ответа модели GPT и его атрибутов
        add_message(user_id=user_id, full_message=[answer_gpt, 'assistant', total_gpt_tokens, tts_symbols, 0])

        if error_message:
            bot.send_message(user_id, error_message)
            return

        # Преобразование текста ответа в речь
        status_tts, voice_response = text_to_speech(answer_gpt)

        # Отправка речевого ответа пользователю
        if status_tts:
            bot.send_voice(user_id, voice_response, reply_to_message_id=message.id)
        else:
            bot.send_message(user_id, answer_gpt, reply_to_message_id=message.id)

    except Exception as e:
        logging.error(e)
        bot.send_message(user_id, "Не получилось ответить. Попробуй записать другое сообщение")


# Обработчик команд '/stt' и '/start'
@bot.message_handler(commands=['stt', 'start'])
def stt_handler(message):
    user_id = message.from_user.id
    bot.send_message(user_id, 'Отправь голосовое сообщение, чтобы я его распознал!')
    bot.register_next_step_handler(message, stt)

# Обработчик голосовых сообщений
def stt(message: Message):
    user_id = message.from_user.id

    # Проверка наличия голосового сообщения
    if not message.voice:
        return

    # Проверка лимита блоков распознавания речи (Speech-to-Text)
    success, stt_blocks = is_stt_block_limit(user_id, message.voice.duration)
    if not success:
        bot.send_message(user_id, stt_blocks)
        return

    # Получение информации о голосовом сообщении и его скачивание
    file_id = message.voice.file_id
    file_info = bot.get_file(file_id)
    file = bot.download_file(file_info.file_path)

    # Преобразование речи в текст
    status, text = speech_to_text(file)

    # Сохранение текста и атрибутов сообщения
    add_message(user_id, [text, 'assistant', 0, 0, stt_blocks])

    # Отправка распознанного текста пользователю
    if status:
        bot.send_message(user_id, text, reply_to_message_id=message.id)
    else:
        bot.send_message(user_id, text)

# Обработчик команды '/tts'
@bot.message_handler(commands=['tts'])
def tts_handler(message):
    user_id = message.from_user.id
    bot.send_message(user_id, 'Отправь следующим сообщением текст, чтобы я его озвучил!')
    bot.register_next_step_handler(message, tts)

# Обработчик текстовых сообщений для генерации ответа
def tts(message: Message):
    user_id = message.from_user.id
    text = message.text

    # Проверка наличия текстового сообщения
    if message.content_type != 'text':
        bot.send_message(user_id, 'Отправь текстовое сообщение')
        return

    # Проверка лимита символов для синтеза речи (Text-to-Speech)
    tts_symbol, error_message = is_tts_symbol_limit(user_id, text)
    if error_message and user_id not in ADMINS_IDS:
        bot.send_message(user_id, error_message)
        return

    # Преобразование текста в речь
    status, content = text_to_speech(text)

    # Сохранение текста и атрибутов сообщения
    add_message(user_id, [text, 'user', 0, tts_symbol, 0])

    # Отправка речевого ответа пользователю
    if status:
        bot.send_voice(user_id, content)
    else:
        bot.send_message(user_id, content)

# Обработчик текстовых сообщений для генерации ответа
@bot.message_handler(content_types=['text'])
def handle_text(message: Message):
    user_id = message.from_user.id

    try:
        # Проверка количества пользователей и их статуса
        status_check_users, error_message = check_number_of_users(user_id)
        if not status_check_users:
            bot.send_message(user_id, error_message)
            return

        # Сохранение текста и атрибутов сообщения пользователя
        full_user_message = [message.text, 'user', 0, 0, 0]
        add_message(user_id=user_id, full_message=full_user_message)

        # Получение последних сообщений пользователя и общего количества потраченных токенов
        last_messages, total_spent_tokens = select_n_last_messages(user_id, COUNT_LAST_MSG)

        # Проверка лимита токенов для модели GPT
        total_gpt_tokens, error_message = is_gpt_token_limit(last_messages, total_spent_tokens, user_id)
        if error_message:
            bot.send_message(user_id, error_message)
            return

        # Запрос к модели GPT для генерации ответа на основе последних сообщений пользователя
        status_gpt, answer_gpt, tokens_in_answer = ask_gpt(last_messages)
        if not status_gpt:
            bot.send_message(user_id, answer_gpt)
            return
        total_gpt_tokens += tokens_in_answer

        # Сохранение текста и атрибутов ответа модели GPT
        full_gpt_message = [answer_gpt, 'assistant', total_gpt_tokens, 0, 0]
        add_message(user_id=user_id, full_message=full_gpt_message)

        # Отправка сгенерированного ответа
        bot.send_message(user_id, answer_gpt, reply_to_message_id=message.id)

    except Exception as e:
        logging.error(e)
        bot.send_message(user_id, "Не получилось ответить. Попробуй написать другое сообщение")

# Запуск бота
if __name__ == '__main__':
    logging.info('programm start')
    create_database()
    bot.infinity_polling()



