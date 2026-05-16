import sqlite3
from contextlib import contextmanager

DB_PATH = "urls.db"


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS urls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                short_code TEXT UNIQUE NOT NULL,
                original_url TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                clicks INTEGER DEFAULT 0
            )
        """)


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def get_all_urls() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT short_code, original_url, created_at, clicks FROM urls ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_stats() -> dict:
    with get_conn() as conn:
        total_links = conn.execute("SELECT COUNT(*) FROM urls").fetchone()[0]
        total_clicks = conn.execute("SELECT COALESCE(SUM(clicks), 0) FROM urls").fetchone()[0]
        today_links = conn.execute(
            "SELECT COUNT(*) FROM urls WHERE DATE(created_at) = DATE('now')"
        ).fetchone()[0]
        return {"total_links": total_links, "total_clicks": total_clicks, "today_links": today_links}
