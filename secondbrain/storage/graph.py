from secondbrain.storage.neo4j_client import session


async def create_user_node(user_id: str, email: str) -> None:
    async with session() as s:
        await s.run(
            """
            MERGE (u:User {id: $id})
            SET u.email = $email, u.created_at = coalesce(u.created_at, datetime())
            """,
            id=user_id,
            email=email,
        )


async def create_notebook_node(notebook_id: str, title: str, owner_user_id: str) -> None:
    async with session() as s:
        await s.run(
            """
            MATCH (u:User {id: $owner_id})
            MERGE (n:Notebook {id: $nb_id})
            SET n.title = $title, n.created_at = coalesce(n.created_at, datetime())
            MERGE (u)-[:OWNS]->(n)
            """,
            owner_id=owner_user_id,
            nb_id=notebook_id,
            title=title,
        )


async def merge_ideas(notebook_id: str, ideas: list[dict]) -> None:
    """ideas: [{"id": str, "label": str, "summary": str, "related_to": [id, ...]}]"""
    async with session() as s:
        for idea in ideas:
            await s.run(
                """
                MATCH (n:Notebook {id: $nb_id})
                MERGE (i:Idea {id: $idea_id})
                SET i.label = $label, i.summary = $summary
                MERGE (n)-[:HAS_IDEA]->(i)
                """,
                nb_id=notebook_id,
                idea_id=idea["id"],
                label=idea["label"],
                summary=idea.get("summary", ""),
            )
        for idea in ideas:
            for rel_id in idea.get("related_to", []):
                await s.run(
                    """
                    MATCH (a:Idea {id: $a_id}), (b:Idea {id: $b_id})
                    MERGE (a)-[:RELATES_TO]->(b)
                    """,
                    a_id=idea["id"],
                    b_id=rel_id,
                )


async def get_notebook_ideas(notebook_id: str) -> list[dict]:
    async with session() as s:
        result = await s.run(
            """
            MATCH (n:Notebook {id: $nb_id})-[:HAS_IDEA]->(i:Idea)
            RETURN i.id AS id, i.label AS label, i.summary AS summary
            """,
            nb_id=notebook_id,
        )
        return [dict(record) async for record in result]
