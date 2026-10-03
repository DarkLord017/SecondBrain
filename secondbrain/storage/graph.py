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
    """ideas: [{"id", "label", "summary", "related_to": [id, ...], "contradicts": [id, ...]}]"""
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
            for con_id in idea.get("contradicts", []):
                await s.run(
                    """
                    MATCH (a:Idea {id: $a_id}), (b:Idea {id: $con_id})
                    MERGE (a)-[:CONTRADICTS]->(b)
                    """,
                    a_id=idea["id"],
                    con_id=con_id,
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


async def get_notebook_contradictions(notebook_id: str) -> list[dict]:
    """Walked by Skeptic — pairs of ideas in this notebook that CONTRADICTS
    edges were written between during idea extraction.
    """
    async with session() as s:
        result = await s.run(
            """
            MATCH (n:Notebook {id: $nb_id})-[:HAS_IDEA]->(a:Idea)-[:CONTRADICTS]->(b:Idea)
            RETURN a.label AS a_label, a.summary AS a_summary, b.label AS b_label, b.summary AS b_summary
            """,
            nb_id=notebook_id,
        )
        return [dict(record) async for record in result]


async def get_notebook_idea_graph(notebook_id: str) -> list[dict]:
    """A real graph walk, not a flat list — each idea plus the labels of
    everything it RELATES_TO. This is what distinguishes Linker from
    Finder's plain vector search: the connections between ideas, not just
    the ideas themselves.
    """
    async with session() as s:
        result = await s.run(
            """
            MATCH (n:Notebook {id: $nb_id})-[:HAS_IDEA]->(i:Idea)
            OPTIONAL MATCH (i)-[:RELATES_TO]-(related:Idea)
            RETURN i.id AS id, i.label AS label, i.summary AS summary,
                   collect(DISTINCT related.label) AS related_labels
            """,
            nb_id=notebook_id,
        )
        return [dict(record) async for record in result]
