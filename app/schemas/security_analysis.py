from pydantic import BaseModel


class SecurityAnalysisOut(BaseModel):
    """The security analysis result for a piece of source code."""
    security_id: int
    report_id: int
    issue_description: str
    severity: str        # "Low" | "Medium" | "High"
    recommendation: str
    security_score: float  # 0-10, higher = more secure

    class Config:
        from_attributes = True