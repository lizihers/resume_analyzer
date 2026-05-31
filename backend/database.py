import json
import os
from urllib.parse import quote_plus
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

# Support both DATABASE_URL and individual env vars
_DB_URL = os.getenv("DATABASE_URL", "")
if _DB_URL:
    DATABASE_URL = _DB_URL
else:
    _host = os.getenv("DB_HOST", "localhost")
    _port = os.getenv("DB_PORT", "5432")
    _user = os.getenv("DB_USER", "postgres")
    _pass = quote_plus(os.getenv("DB_PASSWORD", "postgres"))
    _name = os.getenv("DB_NAME", "postgres")
    DATABASE_URL = f"postgresql://{_user}:{_pass}@{_host}:{_port}/{_name}"

_pool = None


def _get_pool():
    global _pool
    if _pool is None:
        _pool = pool.SimpleConnectionPool(1, 10, DATABASE_URL)
    return _pool


def _get_conn():
    return _pool.getconn()


def _put_conn(conn):
    _pool.putconn(conn)


# ── Init ──────────────────────────────────────────────────────────


def init_db():
    """Create tables if not exists."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS analyses (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    created_at TIMESTAMP DEFAULT NOW(),
                    filename TEXT NOT NULL DEFAULT '',
                    resume_text TEXT NOT NULL DEFAULT '',
                    analysis_json TEXT,
                    match_json TEXT,
                    job_text TEXT
                )
            """)
        conn.commit()
    finally:
        _put_conn(conn)


# ── Users ─────────────────────────────────────────────────────────


def create_user(username: str, password_hash: str) -> int | None:
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (username, password_hash) VALUES (%s, %s) RETURNING id",
                (username, password_hash),
            )
            uid = cur.fetchone()["id"]
        conn.commit()
        return uid
    except Exception:
        conn.rollback()
        return None
    finally:
        _put_conn(conn)


def get_user_by_username(username: str) -> dict | None:
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE username = %s", (username,))
            row = cur.fetchone()
        return dict(row) if row else None
    finally:
        _put_conn(conn)


def get_user_by_id(user_id: int) -> dict | None:
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            row = cur.fetchone()
        return dict(row) if row else None
    finally:
        _put_conn(conn)


# ── Analyses ──────────────────────────────────────────────────────


def save_analysis(user_id: int, filename: str, text: str, analysis_json: str = "") -> int:
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO analyses (user_id, filename, resume_text, analysis_json) VALUES (%s, %s, %s, %s) RETURNING id",
                (user_id, filename, text, analysis_json),
            )
            row_id = cur.fetchone()["id"]
        conn.commit()
        return row_id
    except Exception:
        conn.rollback()
        raise
    finally:
        _put_conn(conn)


def update_match(analysis_id: int, user_id: int, job_text: str, match_json: str):
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE analyses SET match_json = %s, job_text = %s WHERE id = %s AND user_id = %s",
                (match_json, job_text, analysis_id, user_id),
            )
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        _put_conn(conn)


def get_analysis(analysis_id: int, user_id: int) -> dict | None:
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM analyses WHERE id = %s AND user_id = %s",
                (analysis_id, user_id),
            )
            row = cur.fetchone()
        if row is None:
            return None
        d = dict(row)
        for field in ("analysis_json", "match_json"):
            if d.get(field):
                try:
                    d[field] = json.loads(d[field])
                except (json.JSONDecodeError, TypeError):
                    pass
        # Convert datetime to string for JSON compat
        if d.get("created_at"):
            d["created_at"] = str(d["created_at"])
        return d
    finally:
        _put_conn(conn)


def get_all_analyses(user_id: int) -> list[dict]:
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, created_at, filename FROM analyses WHERE user_id = %s ORDER BY id DESC",
                (user_id,),
            )
            rows = cur.fetchall()
        return [{"id": r["id"], "created_at": str(r["created_at"]), "filename": r["filename"]} for r in rows]
    finally:
        _put_conn(conn)


def delete_analysis(analysis_id: int, user_id: int) -> bool:
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM analyses WHERE id = %s AND user_id = %s",
                (analysis_id, user_id),
            )
        conn.commit()
        return cur.rowcount > 0
    except Exception:
        conn.rollback()
        return False
    finally:
        _put_conn(conn)
