from datetime import datetime
from pydantic import BaseModel


class ProjectCreate(BaseModel):
    """What the client sends us when creating a new project."""
    project_name: str
    description: str | None = None
    language: str  # e.g. "Python / FastAPI"


class ProjectOut(BaseModel):
    """What we send back to the client after creating/fetching a project."""
    project_id: int
    project_name: str
    description: str | None
    language: str
    created_at: datetime

    class Config:
        from_attributes = True
