"""
AgriShield — SQLite Database
Tables: farmers, predictions, actions, outcomes
"""
import sqlite3
import json
from datetime import datetime
from config import DATABASE_PATH


def get_conn():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS farmers (
            id                TEXT PRIMARY KEY,
            name              TEXT NOT NULL,
            phone             TEXT NOT NULL,
            village           TEXT NOT NULL,
            district          TEXT NOT NULL,
            crop              TEXT NOT NULL,
            area_acres        REAL DEFAULT 1.0,
            telegram_chat_id  TEXT DEFAULT '',
            language          TEXT DEFAULT 'te',
            created_at        TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Migrate existing DB: add telegram_chat_id column if missing
    try:
        c.execute("ALTER TABLE farmers ADD COLUMN telegram_chat_id TEXT DEFAULT ''")
        print("[DB] Added telegram_chat_id column.")
    except Exception:
        pass  # Column already exists

    try:
        c.execute("ALTER TABLE farmers ADD COLUMN language TEXT DEFAULT 'te'")
        print("[DB] Added language column.")
    except Exception:
        pass  # Column already exists

    c.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            farmer_id   TEXT,
            district    TEXT,
            risk_type   TEXT,
            probability REAL,
            signals     TEXT,
            summary     TEXT,
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS actions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            prediction_id   INTEGER,
            farmer_id       TEXT,
            action_type     TEXT,
            status          TEXT DEFAULT 'pending',
            details         TEXT,
            created_at      TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS outcomes (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            farmer_id       TEXT,
            prediction_id   INTEGER,
            actual_loss_pct REAL,
            claim_filed     INTEGER DEFAULT 0,
            claim_amount    REAL DEFAULT 0.0,
            created_at      TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
    print("[DB] Tables ready.")


def seed_farmers():
    """Seed 5 East Godavari farmers for demo/testing.
    telegram_chat_id is blank — fill in after farmers message @AgriShield_sai_bot.
    """
    farmers = [
        ("EG-001", "Raju Rao",      "+919876543210", "Kovvur",      "East Godavari", "paddy",     2.5, "", "te"),
        ("EG-002", "Lakshmi Devi",  "+919876543211", "Rajahmundry", "East Godavari", "paddy",     1.8, "", "te"),
        ("EG-003", "Venkat Reddy",  "+919876543212", "Amalapuram",  "East Godavari", "banana",    3.0, "", "te"),
        ("EG-004", "Sunita Kumari", "+919876543213", "Kakinada",    "East Godavari", "paddy",     1.2, "", "te"),
        ("EG-005", "Srinu Naidu",   "+919876543214", "Mandapeta",   "East Godavari", "sugarcane", 4.0, "", "te"),
    ]
    conn = get_conn()
    c = conn.cursor()
    for f in farmers:
        c.execute("""
            INSERT OR IGNORE INTO farmers
            (id, name, phone, village, district, crop, area_acres, telegram_chat_id, language)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, f)
    conn.commit()
    conn.close()
    print(f"[DB] Seeded {len(farmers)} farmers.")


def save_prediction(farmer_id, district, risk_type, probability, signals, summary):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO predictions
        (farmer_id, district, risk_type, probability, signals, summary)
        VALUES (?,?,?,?,?,?)
    """, (farmer_id, district, risk_type, probability, json.dumps(signals), summary))
    pred_id = c.lastrowid
    conn.commit()
    conn.close()
    return pred_id


def save_action(prediction_id, farmer_id, action_type, status, details):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO actions
        (prediction_id, farmer_id, action_type, status, details)
        VALUES (?,?,?,?,?)
    """, (prediction_id, farmer_id, action_type, status, json.dumps(details)))
    conn.commit()
    conn.close()


def get_farmers_by_district(district):
    conn = get_conn()
    c = conn.cursor()
    rows = c.execute(
        "SELECT * FROM farmers WHERE district = ?", (district,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_telegram_chat_id(farmer_id: str, chat_id: str):
    """Update a farmer's Telegram chat ID after they've messaged the bot."""
    conn = get_conn()
    conn.execute(
        "UPDATE farmers SET telegram_chat_id = ? WHERE id = ?",
        (chat_id, farmer_id)
    )
    conn.commit()
    conn.close()
    print(f"[DB] Updated telegram_chat_id for {farmer_id} → {chat_id}")


def get_all_telegram_chat_ids() -> list:
    """Return all farmers who have linked their Telegram."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, name, telegram_chat_id FROM farmers WHERE telegram_chat_id != ''"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_recent_predictions(limit=10):
    conn = get_conn()
    c = conn.cursor()
    rows = c.execute("""
        SELECT p.*, f.name, f.village FROM predictions p
        LEFT JOIN farmers f ON p.farmer_id = f.id
        ORDER BY p.created_at DESC LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    init_db()
    seed_farmers()
    print("[DB] Ready.")