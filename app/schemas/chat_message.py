from datetime import datetime
from pydantic import BaseModel


class ChatMessageCreate(BaseModel):
    """What the client sends when sending a message to the AI assistant."""
    message: str


class ChatMessageOut(BaseModel):
    """A chat message and the AI's reply, as sent back to the client."""
    chat_id: int
    project_id: int
    message: str
    ai_response: str | None
    timestamp: datetime

    class Config:
        from_attributes = True