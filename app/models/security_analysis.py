from sqlalchemy import String, Text, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SecurityAnalysis(Base):
    """Maps to the SecurityAnalysis class in the class diagram."""

    __tablename__ = "security_analyses"

    security_id: Mapped[int] = mapped_column(primary_key=True, index=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("analysis_reports.report_id"), nullable=False, unique=True)
    issue_description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)  # Low/Medium/High
    recommendation: Mapped[str] = mapped_column(Text, nullable=False)
    security_score: Mapped[float] = mapped_column(Float, nullable=False)

    report: Mapped["AnalysisReport"] = relationship(back_populates="security_analysis")
