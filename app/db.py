import os
import sqlite3
import threading

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = os.getenv("DB_PATH") or str(BASE_DIR / "gateway.db")

# DB_PATH = os.getenv("DB_PATH", "gateway.db")

_lock = threading.Lock()
_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
_conn.execute("PRAGMA journal_mode=WAL")


def init_db():
    with _lock:
        _conn.execute(
            """
            CREATE TABLE IF NOT EXISTS budgets (
                api_key TEXT PRIMARY KEY,
                used_tokens INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        _conn.execute(
            """
            CREATE TABLE IF NOT EXISTS usage_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                api_key TEXT NOT NULL,
                model TEXT,
                provider TEXT,
                prompt_tokens INTEGER,
                completion_tokens INTEGER,
                total_tokens INTEGER,
                estimated_cost REAL,
                status TEXT NOT NULL,
                error TEXT,
                timestamp TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        _conn.commit()


def get_conn() -> sqlite3.Connection:
    return _conn


def get_lock() -> threading.Lock:
    return _lock
