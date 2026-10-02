from psycopg.rows import dict_row

from secondbrain.storage.db import get_pool


async def create_run(notebook_id: str, user_id: str, question: str) -> dict:
    async with get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                INSERT INTO runs (notebook_id, user_id, question)
                VALUES (%s, %s, %s)
                RETURNING id, notebook_id, user_id, question, status, created_at
                """,
                (notebook_id, user_id, question),
            )
            return await cur.fetchone()


async def update_run_status(
    run_id: str, status: str, final_answer: str | None = None, error: str | None = None
) -> None:
    async with get_pool().connection() as conn:
        await conn.execute(
            """
            UPDATE runs
            SET status = %s, final_answer = COALESCE(%s, final_answer), error = COALESCE(%s, error),
                updated_at = now()
            WHERE id = %s
            """,
            (status, final_answer, error, run_id),
        )


async def get_run(run_id: str) -> dict | None:
    async with get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT id, notebook_id, user_id, question, status, final_answer, error, created_at
                FROM runs WHERE id = %s
                """,
                (run_id,),
            )
            return await cur.fetchone()
