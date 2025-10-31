# modules/botTelegram.py
import os
import telebot
import legalDetails
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# Токен бота
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise ValueError("Не задана переменная окружения TELEGRAM_BOT_TOKEN")

bot = telebot.TeleBot(TOKEN)

# Обработчик команд
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    logger.info(f"Пользователь {message.from_user.id} отправил команду: {message.text}")
    bot.send_message(message.chat.id, "Привет! Отправь мне ИНН (10 цифр), и я покажу данные об организации.")

# Обработчик текстовых сообщений
@bot.message_handler(content_types=['text'])
def echo_message(message):
    user_id = message.from_user.id
    text = message.text.strip()

    # Логируем ID пользователя и сообщение
    logger.info(f"Получено сообщение от пользователя {user_id}: '{text}'")

    # Проверка, что ИНН — это 10 цифр
    if not text.isdigit() or len(text) != 10:
        logger.warning(f"Пользователь {user_id} отправил некорректный ИНН: '{text}'")
        bot.reply_to(message, "Пожалуйста, введите корректный ИНН (10 цифр).")
        return

    try:
        # Получаем JSON-данные
        json_data = legalDetails.get_data(text)

        # Преобразуем JSON в читаемый текст
        response_text = format_legal_info(json_data)

        # Отправляем пользователю
        bot.reply_to(message, response_text)
        logger.info(f"Ответ отправлен пользователю {user_id}")

    except Exception as e:
        error_msg = f"Ошибка при обработке данных для пользователя {user_id}: {str(e)}"
        logger.error(error_msg)
        bot.reply_to(message, f"Ошибка при обработке данных: {str(e)}")

def format_legal_info(data):
    """Форматирует JSON-данные в читаемый текст"""
    if not data or "short" not in data:
        return "Данные не найдены или недоступны."

    short = data["short"]

    # Формируем текст
    lines = [
        "📋 Данные об организации",
        "",
        f"📌 Полное наименование: {short.get('НаимЮЛПолн', '-')}",
        f"🔖 Краткое наименование: {short.get('НаимСокр', '-')}",
        f"🏛  ОПФ (код): {short.get('КодОПФ', '-')}",
        f"🆔 ИНН: {short.get('ИНН', '-')}",
        f"🔖 КПП: {short.get('КПП', '-')}",
        f"🔢 ОГРН: {short.get('ОГРН', '-')}",
        f"📅 Дата образования: {short.get('ДатаОбр', '-')}",
        f"📍  Код региона: {short.get('КодРегиона', '-')}",
        f"📦 ОКВЭД (основной): {short.get('КодОКВЭД', '-')}",
        f"🔢 ОКПО: {short.get('ОКПО', '-')}",
        f"🔢 ОКАТО: {short.get('ОКАТО', '-')}",
        f"🔢 ОКФС: {short.get('ОКФС', '-')}",
        f"🔢 ОКОГУ: {short.get('ОКОГУ', '-')}"
    ]

    return "\n".join(lines)

if __name__ == '__main__':
    logger.info("Telegram-бот запущен. Ожидание сообщений...")
    bot.polling(none_stop=True)