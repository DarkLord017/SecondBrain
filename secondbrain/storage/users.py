from psycopg.rows import dict_row

from secondbrain.storage.db import get_pool


async def create_user(email: str, password_hash: str) -> dict:
    async with get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                INSERT INTO users (email, password_hash)
                VALUES (%s, %s)
                RETURNING id, email, profile_synced, created_at
                """,
                (email, password_hash),
            )
            return await cur.fetchone()


async def get_user_by_email(email: str) -> dict | None:
    async with get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT id, email, password_hash, profile_synced, created_at FROM users WHERE email = %s",
                (email,),
            )
            return await cur.fetchone()


async def set_profile_synced(user_id: str, value: bool) -> None:
    async with get_pool().connection() as conn:
        await conn.execute("UPDATE users SET profile_synced = %s WHERE id = %s", (value, user_id))
