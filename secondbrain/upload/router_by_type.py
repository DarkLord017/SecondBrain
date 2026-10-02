from secondbrain.ingestion.llamaparse_client import parse_handwritten_to_markdown
from secondbrain.integrations.supermemory_client import add_document
from secondbrain.integrations.supermemory_client import upload_file as sm_upload_file

_FILE_TYPE_OVERRIDE = {"image": "image", "video": "video"}


async def ingest_by_type(notebook_id: str, user_id: str, raw: bytes, validated: dict, filename: str) -> dict:
    """Sends the file to Supermemory. Does NOT run idea extraction — the
    caller schedules that as a background task so the upload response
    isn't blocked on Supermemory's own (potentially slow) async parsing.

    Both paths use taskType="superrag": notebook uploads are reference
    material for Finder to search, not personal facts about the user, so
    they skip Supermemory's fact-extraction/profile pipeline (also 5x
    cheaper per token).
    """
    container_tag = f"notebook:{notebook_id}"
    doc_type = validated["doc_type"]

    if doc_type == "handwritten":
        markdown = await parse_handwritten_to_markdown(raw, filename=filename)
        sm_doc = await add_document(
            content=markdown,
            container_tag=container_tag,
            task_type="superrag",
            metadata={"filename": filename, "source": "llamaparse", "user_id": user_id},
        )
        parsed_text = markdown
        sm_document_id = sm_doc.get("id") or sm_doc.get("documentId") or ""
    else:
        sm_doc = await sm_upload_file(
            raw,
            filename=filename,
            container_tags=[container_tag],
            file_type=_FILE_TYPE_OVERRIDE.get(doc_type),
            mime_type=validated["mime"],
            metadata={"user_id": user_id},
            task_type="superrag",
        )
        sm_document_id = sm_doc["id"]
        parsed_text = None  # Supermemory parses async; idea_extraction polls for it.

    return {"supermemory_document_id": sm_document_id, "doc_type": doc_type, "parsed_text": parsed_text}
