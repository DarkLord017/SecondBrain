from pydantic import BaseModel


class UploadResponse(BaseModel):
    document_id: str
    type: str
    status: str


class DocumentStatusOut(BaseModel):
    document_id: str
    status: str
