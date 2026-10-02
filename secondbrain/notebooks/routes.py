from fastapi import APIRouter, HTTPException

from secondbrain.integrations.supermemory_client import write_memory
from secondbrain.notebooks.schemas import CreateNotebookRequest, NotebookOut
from secondbrain.storage import graph as graph_store
from secondbrain.storage import notebooks as notebooks_store

router = APIRouter(prefix="/notebooks", tags=["notebooks"])


def _to_out(row: dict) -> dict:
    return {
        "notebook_id": str(row["id"]),
        "owner_user_id": str(row["owner_user_id"]),
        "title": row["title"],
        "created_at": row["created_at"],
    }


@router.post("", response_model=NotebookOut, status_code=201)
async def create_notebook(req: CreateNotebookRequest):
    nb = await notebooks_store.create_notebook(owner_user_id=req.user_id, title=req.title)
    nb_id = str(nb["id"])

    await write_memory(
        content=f"Notebook created: {req.title}",
        container_tags=[f"user:{req.user_id}", f"notebook:{nb_id}"],
        metadata={"type": "notebook_profile", "title": req.title, "owner_user_id": req.user_id},
    )
    await graph_store.create_notebook_node(notebook_id=nb_id, title=req.title, owner_user_id=req.user_id)

    return _to_out(nb)


@router.get("", response_model=list[NotebookOut])
async def list_notebooks(user_id: str):
    rows = await notebooks_store.list_notebooks(owner_user_id=user_id)
    return [_to_out(r) for r in rows]


@router.get("/{notebook_id}", response_model=NotebookOut)
async def get_notebook(notebook_id: str):
    nb = await notebooks_store.get_notebook(notebook_id)
    if not nb:
        raise HTTPException(404, "notebook not found")
    return _to_out(nb)
