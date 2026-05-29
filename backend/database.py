import sqlite3
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

TZ = timezone(timedelta(hours=8))
DB_PATH = Path(__file__).parent.parent / "data" / "analyses.db"


def get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            filename TEXT NOT NULL DEFAULT '',
            resume_text TEXT NOT NULL DEFAULT '',
            analysis_json TEXT,
            match_json TEXT,
            job_text TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    # Migration: add user_id if upgrading from old schema
    try:
        conn.execute("SELECT user_id FROM analyses LIMIT 0")
    except sqlite3.OperationalError:
        conn.execute("ALTER TABLE analyses ADD COLUMN user_id INTEGER DEFAULT 1")
    conn.commit()
    conn.close()


# ── Users ───────────────────────────────────────────────────────


def create_user(username: str, password_hash: str) -> int | None:
    conn = get_db()
    try:
        c = conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, password_hash),
        )
        conn.commit()
        uid = c.lastrowid
        conn.close()
        return uid
    except sqlite3.IntegrityError:
        conn.close()
        return None


def get_user_by_username(username: str) -> dict | None:
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict | None:
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ── Analyses (scoped to user) ───────────────────────────────────


def save_analysis(user_id: int, filename: str, text: str, analysis_json: str = "") -> int:
    conn = get_db()
    c = conn.execute(
        "INSERT INTO analyses (user_id, filename, resume_text, analysis_json) VALUES (?, ?, ?, ?)",
        (user_id, filename, text, analysis_json),
    )
    conn.commit()
    row_id = c.lastrowid
    conn.close()
    return row_id


def update_match(analysis_id: int, user_id: int, job_text: str, match_json: str):
    conn = get_db()
    conn.execute(
        "UPDATE analyses SET match_json=?, job_text=? WHERE id=? AND user_id=?",
        (match_json, job_text, analysis_id, user_id),
    )
    conn.commit()
    conn.close()


def get_analysis(analysis_id: int, user_id: int) -> dict | None:
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM analyses WHERE id=? AND user_id=?", (analysis_id, user_id)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    d = dict(row)
    for field in ("analysis_json", "match_json"):
        if d.get(field):
            try:
                d[field] = json.loads(d[field])
            except json.JSONDecodeError:
                pass
    return d


def get_all_analyses(user_id: int) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT id, created_at, filename FROM analyses WHERE user_id=? ORDER BY id DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_analysis(analysis_id: int, user_id: int) -> bool:
    conn = get_db()
    c = conn.execute(
        "DELETE FROM analyses WHERE id=? AND user_id=?", (analysis_id, user_id)
    )
    conn.commit()
    deleted = c.rowcount > 0
    conn.close()
    return deleted
