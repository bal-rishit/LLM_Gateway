from fastapi import HTTPException

from app.db import get_conn, get_lock

MONTHLY_BUDGET = 1_000_000  # tokens, per api key


class TokenBudgetLimiter:
    async def check_and_increment(self, api_key: str, estimated_tokens: int) -> int:
        conn = get_conn()
        lock = get_lock()

        with lock:
            conn.execute("BEGIN IMMEDIATE")
            try:
                row = conn.execute(
                    "SELECT used_tokens FROM budgets WHERE api_key = ?", (api_key,)
                ).fetchone()
                current_usage = row[0] if row else 0

                if current_usage + estimated_tokens > MONTHLY_BUDGET:
                    conn.execute("ROLLBACK")
                    raise HTTPException(
                        status_code=429,
                        detail=(
                            f"Monthly token budget exceeded "
                            f"({current_usage}/{MONTHLY_BUDGET} tokens used)"
                        ),
                    )

                if row:
                    conn.execute(
                        "UPDATE budgets SET used_tokens = used_tokens + ? WHERE api_key = ?",
                        (estimated_tokens, api_key),
                    )
                else:
                    conn.execute(
                        "INSERT INTO budgets (api_key, used_tokens) VALUES (?, ?)",
                        (api_key, estimated_tokens),
                    )
                conn.commit()
            except HTTPException:
                raise
            except Exception:
                conn.rollback()
                raise

        return estimated_tokens

    async def reconcile_usage(self, api_key: str, estimated: int, actual: int):
        difference = actual - estimated
        if difference == 0:
            return

        conn = get_conn()
        lock = get_lock()

        with lock:
            conn.execute("BEGIN IMMEDIATE")
            try:
                conn.execute(
                    "UPDATE budgets SET used_tokens = used_tokens + ? WHERE api_key = ?",
                    (difference, api_key),
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    


token_budget_limiter = TokenBudgetLimiter()
