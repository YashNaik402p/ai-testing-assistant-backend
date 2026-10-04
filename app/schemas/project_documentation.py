from datetime import datetime
from pydantic import BaseModel


class ProjectDocumentationOut(BaseModel):
    project_documentation_id: int
    project_id: int
    content: str
    generated_at: datetime

    class Config:
        from_attributes = True