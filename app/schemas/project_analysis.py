from datetime import datetime
from pydantic import BaseModel


class ProjectAnalysisOut(BaseModel):
    project_analysis_id: int
    project_id: int
    overview: str
    security_summary: str
    average_quality_score: float | None
    average_security_score: float | None
    average_complexity: str | None
    total_files: int
    files_with_analysis: int
    files_with_security: int
    created_at: datetime

    class Config:
        from_attributes = True