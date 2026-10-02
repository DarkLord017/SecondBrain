from secondbrain.storage.db import get_pool


async def record(run_id: str, notebook_id: str, user_id: str, cost_cents: int, tokens_in: int = 0, tokens_out: int = 0) -> None:
    async with get_pool().connection() as conn:
        await conn.execute(
            """
            INSERT INTO run_ledger (run_id, notebook_id, user_id, tokens_in, tokens_out, cost_cents)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (run_id, notebook_id, user_id, tokens_in, tokens_out, cost_cents),
        )
