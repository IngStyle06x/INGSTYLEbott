import io
from datetime import date

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from db_handler import get_records_between, period_dates

MOOD_EMOJI = {1: "😞", 2: "😐", 3: "🙂", 4: "😊", 5: "🤩"}

WEEKDAYS = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]


def period_summary(user_id, days, label):
    """Текстовая сводка за N дней."""
    start, end = period_dates(days)
    records = get_records_between(user_id, start, end)

    if not records:
        return f"За {label} нет записей. Добавь данные через /add."

    count = len(records)
    total_mood = 0
    total_work = 0
    total_sleep = 0
    best_mood = 0
    worst_mood = 6
    best_date = ""
    worst_date = ""

    for row in records:
        total_mood += row["mood"]
        total_work += row["work_hours"]
        total_sleep += row["sleep_hours"]

        if row["mood"] > best_mood:
            best_mood = row["mood"]
            d = date.fromisoformat(row["date"]).strftime("%d.%m.%Y")
            best_date = f"{d} ({MOOD_EMOJI[row['mood']]} {row['mood']})"

        if row["mood"] < worst_mood:
            worst_mood = row["mood"]
            d = date.fromisoformat(row["date"]).strftime("%d.%m.%Y")
            worst_date = f"{d} ({MOOD_EMOJI[row['mood']]} {row['mood']})"

    avg_mood = total_mood / count
    avg_work = total_work / count
    avg_sleep = total_sleep / count

    return (
        f"📊 Сводка {label}\n\n"
        f"• Среднее настроение: {avg_mood:.2f}\n"
        f"• Средние часы работы: {avg_work:.2f} ч\n"
        f"• Средние часы сна: {avg_sleep:.2f} ч\n"
        f"• Лучший день: {best_date}\n"
        f"• Худший день: {worst_date}"
    )


def generate_insights(user_id):
    """Три простых вывода на основе записей за 30 дней."""
    start, end = period_dates(30)
    records = get_records_between(user_id, start, end)

    if len(records) < 3:
        return "Мало данных. Нужно минимум 3 записи за 30 дней."

    # 1. Настроение по дням недели
    mood_by_day = {}  # {0: [3, 4], 1: [2, 5], ...}  0 = понедельник
    for row in records:
        weekday = date.fromisoformat(row["date"]).weekday()
        if weekday not in mood_by_day:
            mood_by_day[weekday] = []
        mood_by_day[weekday].append(row["mood"])

    best_day_num = 0
    worst_day_num = 0
    best_avg = 0
    worst_avg = 6

    for weekday, moods in mood_by_day.items():
        avg = sum(moods) / len(moods)
        if avg > best_avg:
            best_avg = avg
            best_day_num = weekday
        if avg < worst_avg:
            worst_avg = avg
            worst_day_num = weekday

    insight1 = (
        f"Настроение выше в {WEEKDAYS[best_day_num]} (среднее {best_avg:.2f}), "
        f"ниже — в {WEEKDAYS[worst_day_num]} (среднее {worst_avg:.2f})."
    )

    # 2. Работа и настроение
    work_hours_list = [row["work_hours"] for row in records]
    work_hours_list.sort()
    median_work = work_hours_list[len(work_hours_list) // 2]

    mood_when_much_work = []
    mood_when_little_work = []
    for row in records:
        if row["work_hours"] >= median_work:
            mood_when_much_work.append(row["mood"])
        else:
            mood_when_little_work.append(row["mood"])

    if mood_when_much_work and mood_when_little_work:
        avg_much = sum(mood_when_much_work) / len(mood_when_much_work)
        avg_little = sum(mood_when_little_work) / len(mood_when_little_work)
        diff = avg_much - avg_little

        if abs(diff) < 0.15:
            insight2 = f"Работа слабо влияет на настроение (много работы: {avg_much:.2f}, мало: {avg_little:.2f})."
        elif diff < 0:
            insight2 = f"При большой нагрузке настроение ниже ({avg_much:.2f} vs {avg_little:.2f})."
        else:
            insight2 = f"При большой нагрузке настроение выше ({avg_much:.2f} vs {avg_little:.2f})."
    else:
        insight2 = "Недостаточно данных по часам работы."

    # 3. Сон и продуктивность
    sleep_hours_list = [row["sleep_hours"] for row in records]
    sleep_hours_list.sort()
    median_sleep = sleep_hours_list[len(sleep_hours_list) // 2]

    work_when_much_sleep = []
    work_when_little_sleep = []
    for row in records:
        if row["sleep_hours"] >= median_sleep:
            work_when_much_sleep.append(row["work_hours"])
        else:
            work_when_little_sleep.append(row["work_hours"])

    if work_when_much_sleep and work_when_little_sleep:
        avg_much = sum(work_when_much_sleep) / len(work_when_much_sleep)
        avg_little = sum(work_when_little_sleep) / len(work_when_little_sleep)
        diff = avg_much - avg_little

        if abs(diff) < 0.3:
            insight3 = f"Сон слабо влияет на работу (много сна: {avg_much:.1f} ч, мало: {avg_little:.1f} ч)."
        elif diff > 0:
            insight3 = f"При большем сне работаешь больше ({avg_much:.1f} ч vs {avg_little:.1f} ч)."
        else:
            insight3 = f"При меньшем сне работаешь не меньше ({avg_little:.1f} ч vs {avg_much:.1f} ч)."
    else:
        insight3 = "Недостаточно данных по сну."

    return (
        "🔍 Мои инсайты\n\n"
        f"📅 Дни недели\n{insight1}\n\n"
        f"💼 Работа и настроение\n{insight2}\n\n"
        f"😴 Сон и работа\n{insight3}"
    )


def generate_chart(user_id):
    """Картинка-график за 7 дней. Возвращает BytesIO или None."""
    start, end = period_dates(7)
    records = get_records_between(user_id, start, end)

    if not records:
        return None

    dates = []
    moods = []
    sleep_list = []
    work_list = []

    for row in records:
        dates.append(date.fromisoformat(row["date"]).strftime("%d.%m"))
        moods.append(row["mood"])
        sleep_list.append(row["sleep_hours"])
        work_list.append(row["work_hours"])

    x = list(range(len(dates)))

    fig, ax1 = plt.subplots(figsize=(10, 5))
    ax1.plot(x, moods, marker="o", color="blue", label="Настроение")
    ax1.set_ylim(0.5, 5.5)
    ax1.set_xticks(x)
    ax1.set_xticklabels(dates, rotation=45)
    ax1.grid(True, alpha=0.3)

    ax2 = ax1.twinx()
    ax2.plot(x, sleep_list, marker="s", color="green", linestyle="--", label="Сон")
    ax2.plot(x, work_list, marker="^", color="orange", linestyle="--", label="Работа")

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")

    plt.title("Настроение, сон и работа — 7 дней")
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=120)
    buf.seek(0)
    plt.close(fig)
    return buf


def format_history_entry(row):
    """Одна запись для команды /history."""
    d = date.fromisoformat(row["date"]).strftime("%d.%m.%Y")
    mood = row["mood"]
    text = (
        f"📅 {d}\n"
        f"  Настроение: {MOOD_EMOJI[mood]} ({mood}/5)\n"
        f"  Работа: {row['work_hours']} ч | Сон: {row['sleep_hours']} ч"
    )
    if row["comment"]:
        text += f"\n  💬 {row['comment']}"
    return text
