from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Request, UploadFile

from secondbrain.config import settings
from secondbrain.gateway.throttle import ThrottleExceeded, check_rate_limit
from secondbrain.ingestion.idea_extraction import extract_and_store_ideas
from secondbrain.storage import documents as documents_store
from secondbrain.upload.guardrails import GuardrailError, sniff_and_validate
from secondbrain.upload.quota import UploadQuotaExceeded, reserve_upload_quota, settle_upload_quota
from secondbrain.upload.router_by_type import ingest_by_type
from secondbrain.upload.scanner import get_scanner
from secondbrain.upload.schemas import DocumentStatusOut, UploadResponse

router = APIRouter(prefix="/notebooks", tags=["upload"])

@router.post("/{notebook_id}/upload", response_model=UploadResponse, status_code=202)
async def upload(
    notebook_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    user_id: str = Form(...),
    file: UploadFile = File(...),
    is_handwritten: bool = Form(False),
):
    redis = request.app.state.redis
    raw = await file.read()

    try:
        await check_rate_limit(redis, user_id, notebook_id, settings.throttle_per_min)
    except ThrottleExceeded as e:
        raise HTTPException(429, str(e))

    try:
        validated = sniff_and_validate(
            raw, filename=file.filename or "upload", is_handwritten_hint=is_handwritten
        )
    except GuardrailError as e:
        raise HTTPException(400, str(e))

    if not await get_scanner().scan(raw):
        raise HTTPException(400, "file failed malware scan")

    try:
        reservation = await reserve_upload_quota(
            redis, user_id, notebook_id, validated["size"], settings.upload_quota_bytes_per_day
        )
    except UploadQuotaExceeded as e:
        raise HTTPException(402, str(e))

    try:
        result = await ingest_by_type(
            notebook_id=notebook_id, user_id=user_id, raw=raw, validated=validated, filename=file.filename or "upload"
        )
    except Exception:
        await settle_upload_quota(redis, reservation, validated["size"], success=False)
        raise HTTPException(502, "ingestion failed")

    doc = await documents_store.create_document(
        notebook_id=notebook_id,
        supermemory_document_id=result["supermemory_document_id"],
        doc_type=result["doc_type"],
    )

    background_tasks.add_task(
        extract_and_store_ideas,
        document_id=str(doc["id"]),
        notebook_id=notebook_id,
        supermemory_document_id=result["supermemory_document_id"],
        parsed_text=result["parsed_text"],
    )

    return {"document_id": str(doc["id"]), "type": result["doc_type"], "status": "queued"}


@router.get("/{notebook_id}/documents/{document_id}", response_model=DocumentStatusOut)
async def get_document_status(notebook_id: str, document_id: str):
    doc = await documents_store.get_document(document_id)
    if not doc or str(doc["notebook_id"]) != notebook_id:
        raise HTTPException(404, "document not found")
    return {"document_id": str(doc["id"]), "status": doc["status"]}
