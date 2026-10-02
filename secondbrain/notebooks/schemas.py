from datetime import datetime

from pydantic import BaseModel


class CreateNotebookRequest(BaseModel):
    user_id: str
    title: str


class NotebookOut(BaseModel):
    notebook_id: str
    owner_user_id: str
    title: str
    created_at: datetime
