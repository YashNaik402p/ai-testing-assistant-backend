from datetime import datetime
from pydantic import BaseModel


class DocumentationOut(BaseModel):
    """The generated documentation for a piece of source code."""
    doc_id: int
    report_id: int
    content: str
    generated_at: datetime

    class Config:
        from_attributes = True