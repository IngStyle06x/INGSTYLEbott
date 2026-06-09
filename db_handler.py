import sqlite3
from datetime import date, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "tracker.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        sql = SCHEMA_PATH.read_text(encoding="utf-8")
        conn.executescript(sql)
        conn.commit()


def today():
    return date.today().isoformat()


def has_record_today(user_id):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM daily_records WHERE user_id = ? AND date = ?",
            (user_id, today()),
        ).fetchone()
    return row is not None


def add_record(user_id, mood, work_hours, sleep_hours, comment=None, record_date=None):
    if record_date is None:
        record_date = today()

    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO daily_records "
                "(user_id, date, mood, work_hours, sleep_hours, comment) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, record_date, mood, work_hours, sleep_hours, comment),
            )
            conn.commit()
        return True
    except sqlite3.IntegrityError:
        # Запись за эту дату уже есть
        return False


def get_records_between(user_id, start_date, end_date):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM daily_records "
            "WHERE user_id = ? AND date >= ? AND date <= ? "
            "ORDER BY date ASC",
            (user_id, start_date, end_date),
        ).fetchall()
    return rows


def get_last_records(user_id, limit=7):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM daily_records WHERE user_id = ? ORDER BY date DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return rows


def delete_user_records(user_id):
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM daily_records WHERE user_id = ?", (user_id,))
        conn.commit()
        return cursor.rowcount


def get_reminder_time(user_id):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT reminder_time FROM user_settings WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    if row:
        return row["reminder_time"]
    return None


def set_reminder_time(user_id, reminder_time):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO user_settings (user_id, reminder_time) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET reminder_time = excluded.reminder_time",
            (user_id, reminder_time),
        )
        conn.commit()


def get_all_reminder_settings():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT user_id, reminder_time FROM user_settings WHERE reminder_time IS NOT NULL"
        ).fetchall()
    result = []
    for row in rows:
        result.append((row["user_id"], row["reminder_time"]))
    return result


def period_dates(days):
    """Даты начала и конца периода (последние N дней, включая сегодня)."""
    end = date.today()
    start = end - timedelta(days=days - 1)
    return start.isoformat(), end.isoformat()


if __name__ == "__main__":
    init_db()
    print(f"База создана: {DB_PATH}")
