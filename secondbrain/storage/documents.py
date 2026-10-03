from psycopg.rows import dict_row

from secondbrain.storage.db import get_pool


async def create_document(notebook_id: str, supermemory_document_id: str, doc_type: str) -> dict:
    async with get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                INSERT INTO documents (notebook_id, supermemory_document_id, doc_type)
                VALUES (%s, %s, %s)
                RETURNING id, notebook_id, supermemory_document_id, doc_type, status, retry_count, created_at
                """,
                (notebook_id, supermemory_document_id, doc_type),
            )
            return await cur.fetchone()


async def update_document_status(document_id: str, status: str) -> None:
    async with get_pool().connection() as conn:
        await conn.execute(
            "UPDATE documents SET status = %s WHERE id = %s", (status, document_id)
        )


async def get_document(document_id: str) -> dict | None:
    async with get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT id, notebook_id, supermemory_document_id, doc_type, status, retry_count, created_at
                FROM documents WHERE id = %s
                """,
                (document_id,),
            )
            return await cur.fetchone()


async def list_documents_by_status(status: str) -> list[dict]:
    async with get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT id, notebook_id, supermemory_document_id, doc_type, status, retry_count, created_at
                FROM documents WHERE status = %s
                """,
                (status,),
            )
            return await cur.fetchall()


async def increment_retry_count(document_id: str) -> int:
    async with get_pool().connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "UPDATE documents SET retry_count = retry_count + 1 WHERE id = %s RETURNING retry_count",
                (document_id,),
            )
            row = await cur.fetchone()
            return row["retry_count"]
