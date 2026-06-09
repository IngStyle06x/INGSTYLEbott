CREATE TABLE IF NOT EXISTS daily_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    date DATE NOT NULL,
    mood INTEGER NOT NULL CHECK (mood BETWEEN 1 AND 5),
    work_hours REAL NOT NULL,
    sleep_hours REAL NOT NULL,
    comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, date)
);

CREATE INDEX IF NOT EXISTS idx_daily_records_user_id ON daily_records (user_id);
CREATE INDEX IF NOT EXISTS idx_daily_records_date ON daily_records (date);

CREATE TABLE IF NOT EXISTS user_settings (
    user_id INTEGER PRIMARY KEY,
    reminder_time TEXT
);
