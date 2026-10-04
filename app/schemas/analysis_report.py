from datetime import datetime
from pydantic import BaseModel


class AnalysisReportOut(BaseModel):
    """What we send back after analyzing a piece of source code."""
    report_id: int
    code_id: int
    explanation_summary: str | None
    complexity: str | None       # "Low" | "Medium" | "High"
    quality_score: float | None  # 0-10
    created_at: datetime

    class Config:
        from_attributes = True
