from datetime import datetime, timezone
from typing import Optional

from app.db import get_conn, get_lock
from app.db import init_db as _init_db

COST_PER_1K_TOKENS = {
    "gpt-4o-mini": 0.00030,
    "gpt-4o": 0.0050,
    "gemini/gemini-2.5-flash": 0.00030,
    "gemini/gemini-2.5-flash-lite": 0.00025,
    "gemini/gemini-1.5-pro": 0.00250,
}
DEFAULT_COST_PER_1K = 0.00100


def init_db():
    _init_db()


def estimate_cost(model: str, total_tokens: int) -> float:
    rate = COST_PER_1K_TOKENS.get(model, DEFAULT_COST_PER_1K)
    return round((total_tokens / 1000) * rate, 6)


def log_usage(
    api_key: str,
    model: Optional[str],
    provider: Optional[str],
    prompt_tokens: Optional[int],
    completion_tokens: Optional[int],
    total_tokens: Optional[int],
    status: str,
    error: Optional[str] = None,
):
    cost = estimate_cost(model or "", total_tokens or 0)
    conn = get_conn()
    lock = get_lock()

    with lock:
        conn.execute(
            """
            INSERT INTO usage_log (
                api_key, model, provider, prompt_tokens, completion_tokens,
                total_tokens, estimated_cost, status, error, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                api_key,
                model,
                provider,
                prompt_tokens,
                completion_tokens,
                total_tokens,
                cost,
                status,
                error,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()


def get_usage(api_key: str) -> dict:
    conn = get_conn()
    row = conn.execute(
        """
        SELECT
            COUNT(*) AS request_count,
            COALESCE(SUM(total_tokens), 0) AS total_tokens,
            COALESCE(SUM(estimated_cost), 0) AS total_cost
        FROM usage_log
        WHERE api_key = ? AND status = 'success'
        """,
        (api_key,),
    ).fetchone()

    return {
        "api_key": api_key,
        "request_count": row[0],
        "total_tokens": row[1],
        "estimated_cost_usd": round(row[2], 6),
    }
