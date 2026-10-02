from pydantic import BaseModel


class ChatRequest(BaseModel):
    user_id: str
    question: str


class ChatAck(BaseModel):
    run_id: str
    status: str
