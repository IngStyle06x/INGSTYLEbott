import threading
from datetime import datetime, timedelta

import telebot
from telebot import types

import analyzer
import db_handler


BOT_TOKEN = "8530439375:AAFEZOcpatuh0NK6Ub92TD8_ehPc3IZNxCo"
if not BOT_TOKEN:
    raise RuntimeError("Не задан BOT_TOKEN. Укажите переменную окружения BOT_TOKEN.")

bot = telebot.TeleBot(BOT_TOKEN)

user_data = {}

reminder_timers = {}

# Текст кнопок главного меню
BTN_ADD = "➕ Записать день"
BTN_STATS = "📊 Статистика"
BTN_HISTORY = "📋 История"
BTN_SETTINGS = "⚙️ Настройки"

# Смайлики для настроения 1-5
MOOD_EMOJI = {1: "😞", 2: "😐", 3: "🙂", 4: "😊", 5: "🤩"}


# --- Клавиатуры ---


def make_inline_keyboard(buttons, row_width=1):
    """buttons — список пар (текст_кнопки, callback_data)."""
    keyboard = types.InlineKeyboardMarkup(row_width=row_width)
    for text, data in buttons:
        keyboard.add(types.InlineKeyboardButton(text, callback_data=data))
    return keyboard


# Главное меню (кнопки внизу экрана)
main_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
main_keyboard.row(BTN_ADD, BTN_STATS)
main_keyboard.row(BTN_HISTORY, BTN_SETTINGS)

# Кнопки настроения
mood_buttons = []
for i in range(1, 6):
    mood_buttons.append((f"{i} {MOOD_EMOJI[i]}", f"mood_{i}"))
mood_keyboard = make_inline_keyboard(mood_buttons, row_width=5)

# Кнопки статистики
stats_keyboard = make_inline_keyboard([
    ("📅 За неделю", "stats_week"),
    ("🗓 За месяц", "stats_month"),
    ("🔍 Мои инсайты", "stats_insights"),
    ("📉 График", "stats_chart"),
])

skip_keyboard = make_inline_keyboard([("Пропустить", "comment_skip")])


def work_hours_keyboard():
    return make_inline_keyboard([
        ("0.5 ч", "work_0.5"),
        ("1 ч", "work_1"),
        ("2 ч", "work_2"),
        ("4 ч", "work_4"),
        ("Другое...", "work_other"),
    ], row_width=3)


def sleep_hours_keyboard():
    return make_inline_keyboard([
        ("6 ч", "sleep_6"),
        ("7 ч", "sleep_7"),
        ("8 ч", "sleep_8"),
        ("9 ч", "sleep_9"),
        ("Другое...", "sleep_other"),
    ], row_width=4)





def send(chat_id, text, keyboard=None):
    if keyboard is None:
        keyboard = main_keyboard
    bot.send_message(chat_id, text, reply_markup=keyboard)


def get_step(user_id):
    if user_id not in user_data:
        return None
    return user_data[user_id].get("step")


def clear_user(user_id):
    if user_id in user_data:
        del user_data[user_id]


def is_valid_time(text):
    """Проверяет формат времени ЧЧ:ММ."""
    if ":" not in text:
        return False
    parts = text.split(":")
    if len(parts) != 2:
        return False
    try:
        hour = int(parts[0])
        minute = int(parts[1])
        if hour < 0 or hour > 23:
            return False
        if minute < 0 or minute > 59:
            return False
        return True
    except ValueError:
        return False


def parse_hours(text):
    try:
        value = float(text.replace(",", ".").strip())
        if 0 <= value <= 24:
            return value
    except ValueError:
        pass
    return None


def save_record(chat_id, user_id, comment=None):
    data = user_data.get(user_id, {})
    mood = data.get("mood")
    work = data.get("work_hours")
    sleep = data.get("sleep_hours")

    if mood is None or work is None or sleep is None:
        clear_user(user_id)
        send(chat_id, "Ошибка: данные неполные. Начни заново с /add")
        return

    ok = db_handler.add_record(user_id, mood, work, sleep, comment)
    clear_user(user_id)

    if not ok:
        send(chat_id, "⚠️ Запись за сегодня уже существует.")
        return

    text = (
        f"✅ Запись сохранена!\n\n"
        f"Настроение: {MOOD_EMOJI[mood]} ({mood}/5)\n"
        f"Работа: {work} ч\n"
        f"Сон: {sleep} ч"
    )
    if comment:
        text += f"\nКомментарий: {comment}"
    send(chat_id, text)




def get_seconds_until(time_str):
    now = datetime.now()
    hour, minute = map(int, time_str.split(":"))
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target = target + timedelta(days=1)
    return (target - now).total_seconds()


def send_reminder(user_id):
    try:
        send(user_id, "⏰ Напоминание: не забудь записать день! Нажми «➕ Записать день» или /add")
    except Exception:
        pass


def start_reminder(user_id, time_str):
    if user_id in reminder_timers:
        reminder_timers[user_id].cancel()

    def on_time():
        send_reminder(user_id)
        start_reminder(user_id, time_str)

    timer = threading.Timer(get_seconds_until(time_str), on_time)
    timer.daemon = True
    timer.start()
    reminder_timers[user_id] = timer


# Команды


@bot.message_handler(commands=["start"])
def cmd_start(message):
    send(
        message.chat.id,
        "👋 Привет! Я трекер настроения и продуктивности.\n\n"
        "Каждый день записывай настроение, часы работы и сон — "
        "я покажу статистику, инсайты и графики.\n\n"
        "Команды:\n"
        "/add — записать день\n"
        "/stats — статистика\n"
        "/history — последние записи\n"
        "/settings — напоминание\n"
        "/help — справка",
    )


@bot.message_handler(commands=["help"])
def cmd_help(message):
    send(
        message.chat.id,
        "📖 Справка\n\n"
        "/start — приветствие\n"
        "/add — пошаговый ввод за сегодня\n"
        "/stats — неделя, месяц, инсайты, график\n"
        "/history — последние 7 записей\n"
        "/settings — время напоминания (ЧЧ:ММ)\n"
        "/clear — удалить все записи\n"
        "/help — эта справка",
    )


@bot.message_handler(commands=["add"])
@bot.message_handler(func=lambda m: m.text == BTN_ADD)
def cmd_add(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    if db_handler.has_record_today(user_id):
        send(chat_id, "⚠️ Запись за сегодня уже есть. Можно только одна запись в день.")
        return

    user_data[user_id] = {"step": "mood"}
    bot.send_message(
        chat_id,
        "Оцени настроение от 1 до 5 (1 — ужасно, 5 — отлично):",
        reply_markup=mood_keyboard,
    )


@bot.message_handler(commands=["stats"])
@bot.message_handler(func=lambda m: m.text == BTN_STATS)
def cmd_stats(message):
    bot.send_message(message.chat.id, "Что хочешь узнать?", reply_markup=stats_keyboard)


@bot.message_handler(commands=["history"])
@bot.message_handler(func=lambda m: m.text == BTN_HISTORY)
def cmd_history(message):
    user_id = message.from_user.id
    records = db_handler.get_last_records(user_id, 7)

    if not records:
        send(message.chat.id, "История пуста. Добавь первую запись через /add.")
        return

    text = "📋 Последние записи:\n\n"
    for row in reversed(records):
        text += analyzer.format_history_entry(row) + "\n\n"
    send(message.chat.id, text.strip())


@bot.message_handler(commands=["settings"])
@bot.message_handler(func=lambda m: m.text == BTN_SETTINGS)
def cmd_settings(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    current = db_handler.get_reminder_time(user_id)
    hint = ""
    if current:
        hint = f"\n\nТекущее время: {current}"

    user_data[user_id] = {"step": "settings_time"}
    bot.send_message(
        chat_id,
        f"⚙️ Введи время напоминания в формате ЧЧ:ММ (например, 21:00).{hint}",
        reply_markup=types.ReplyKeyboardRemove(),
    )


@bot.message_handler(commands=["clear"])
def cmd_clear(message):
    keyboard = make_inline_keyboard([
        ("✅ Да, удалить всё", "clear_yes"),
        ("❌ Отмена", "clear_no"),
    ], row_width=2)
    bot.send_message(
        message.chat.id,
        "⚠️ Удалить все записи? Это нельзя отменить.",
        reply_markup=keyboard,
    )


# Нажатия на inline-кнопки


@bot.callback_query_handler(func=lambda call: True)
def on_button_click(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    data = call.data

    bot.answer_callback_query(call.id)

    # Статистика
    if data == "stats_week":
        send(chat_id, analyzer.period_summary(user_id, 7, "неделю"))
        return

    if data == "stats_month":
        send(chat_id, analyzer.period_summary(user_id, 30, "месяц"))
        return

    if data == "stats_insights":
        send(chat_id, analyzer.generate_insights(user_id))
        return

    if data == "stats_chart":
        chart = analyzer.generate_chart(user_id)
        if chart:
            bot.send_photo(chat_id, chart, caption="📉 График за 7 дней", reply_markup=main_keyboard)
        else:
            send(chat_id, "Нет данных для графика.")
        return

    # Очистка данных
    if data == "clear_no":
        send(chat_id, "Отменено.")
        return

    if data == "clear_yes":
        count = db_handler.delete_user_records(user_id)
        send(chat_id, f"✅ Удалено записей: {count}.")
        return

    # Ввод записи: настроение
    if data.startswith("mood_") and get_step(user_id) == "mood":
        mood = int(data.split("_")[1])
        user_data[user_id] = {"step": "work", "mood": mood}
        bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
        bot.send_message(chat_id, "Сколько часов работы/учёбы?", reply_markup=work_hours_keyboard())
        return

    # Ввод записи: часы работы
    if data.startswith("work_") and get_step(user_id) in ("work", "work_custom"):
        if data == "work_other":
            user_data[user_id]["step"] = "work_custom"
            bot.send_message(chat_id, "Введи часы работы числом (например, 3.5):")
            return

        work_hours = float(data.replace("work_", ""))
        mood = user_data[user_id]["mood"]
        user_data[user_id] = {"step": "sleep", "mood": mood, "work_hours": work_hours}
        bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
        bot.send_message(chat_id, "Сколько часов спал?", reply_markup=sleep_hours_keyboard())
        return

    # Ввод записи: часы сна
    if data.startswith("sleep_") and get_step(user_id) in ("sleep", "sleep_custom"):
        if data == "sleep_other":
            user_data[user_id]["step"] = "sleep_custom"
            bot.send_message(chat_id, "Введи часы сна числом (например, 7.5):")
            return

        sleep_hours = float(data.replace("sleep_", ""))
        user_data[user_id]["step"] = "comment"
        user_data[user_id]["sleep_hours"] = sleep_hours
        bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
        bot.send_message(
            chat_id,
            "Добавить комментарий? Напиши текст или нажми «Пропустить»",
            reply_markup=skip_keyboard,
        )
        return

    # Пропуск комментария
    if data == "comment_skip" and get_step(user_id) == "comment":
        save_record(chat_id, user_id, comment=None)
        return


# Текстовые сообщения


@bot.message_handler(content_types=["text"])
def on_text(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    text = message.text.strip()
    step = get_step(user_id)

# Настройка времени напоминания
    if step == "settings_time":
        if not is_valid_time(text):
            bot.send_message(chat_id, "Неверный формат. Введи ЧЧ:ММ (например, 09:30).")
            return
        hour, minute = map(int, text.split(":"))
        time_str = f"{hour:02d}:{minute:02d}"
        db_handler.set_reminder_time(user_id, time_str)
        start_reminder(user_id, time_str)
        clear_user(user_id)
        send(chat_id, f"✅ Напоминание установлено на {time_str}.")
        return

    # Ручной ввод часов работы
    if step == "work_custom":
        hours = parse_hours(text)
        if hours is None:
            bot.send_message(chat_id, "Введи число от 0 до 24.")
            return
        mood = user_data[user_id]["mood"]
        user_data[user_id] = {"step": "sleep", "mood": mood, "work_hours": hours}
        bot.send_message(chat_id, "Сколько часов спал?", reply_markup=sleep_hours_keyboard())
        return

    # Ручной ввод часов сна
    if step == "sleep_custom":
        hours = parse_hours(text)
        if hours is None:
            bot.send_message(chat_id, "Введи число от 0 до 24.")
            return
        user_data[user_id]["step"] = "comment"
        user_data[user_id]["sleep_hours"] = hours
        bot.send_message(
            chat_id,
            "Добавить комментарий? Напиши текст или нажми «Пропустить»",
            reply_markup=skip_keyboard,
        )
        return

    # Комментарий к записи
    if step == "comment":
        save_record(chat_id, user_id, comment=text)
        return

    # Пользователь пишет текст, но должен нажимать кнопки
    if step in ("mood", "work", "sleep"):
        bot.send_message(chat_id, "Используй кнопки выше или начни заново с /add")


# Запуск


def main():
    if not db_handler.DB_PATH.exists():
        db_handler.init_db()

    commands = [
        types.BotCommand("start", "Приветствие"),
        types.BotCommand("add", "Записать день"),
        types.BotCommand("stats", "Статистика"),
        types.BotCommand("history", "История"),
        types.BotCommand("settings", "Напоминание"),
        types.BotCommand("clear", "Очистить данные"),
        types.BotCommand("help", "Справка"),
    ]
    try:
        bot.set_my_commands(commands)
    except Exception as e:
        print(f"Не удалось установить меню команд: {e}")

    # Восстанавливаем напоминания после перезапуска
    for user_id, time_str in db_handler.get_all_reminder_settings():
        try:
            start_reminder(user_id, time_str)
        except Exception:
            pass

    print("Бот запущен...")
    bot.infinity_polling()


if __name__ == "__main__":
    main()
