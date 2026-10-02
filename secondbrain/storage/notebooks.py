from psycopg.rows import dict_row

from secondbrain.storage.db import get_pool


async def create_notebook(owner_user_id: str, title: str) -> dict:
    async with get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                INSERT INTO notebooks (owner_user_id, title)
                VALUES (%s, %s)
                RETURNING id, owner_user_id, title, created_at
                """,
                (owner_user_id, title),
            )
            return await cur.fetchone()


async def list_notebooks(owner_user_id: str) -> list[dict]:
    async with get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT id, owner_user_id, title, created_at
                FROM notebooks WHERE owner_user_id = %s
                ORDER BY created_at DESC
                """,
                (owner_user_id,),
            )
            return await cur.fetchall()


async def get_notebook(notebook_id: str) -> dict | None:
    async with get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT id, owner_user_id, title, created_at FROM notebooks WHERE id = %s",
                (notebook_id,),
            )
            return await cur.fetchone()
