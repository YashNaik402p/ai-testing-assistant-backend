from datetime import datetime
from pydantic import BaseModel


class SourceCodeCreate(BaseModel):
    """What the client sends us when uploading or pasting source code."""
    file_name: str | None = None   # optional — pasted code often won't have one
    code_content: str              # the actual code, as plain text
    language: str                  # e.g. "Python"


class SourceCodeOut(BaseModel):
    """What we send back after saving source code."""
    code_id: int
    project_id: int
    file_name: str
    code_content: str
    language: str
    uploaded_at: datetime

    class Config:
        from_attributes = True
