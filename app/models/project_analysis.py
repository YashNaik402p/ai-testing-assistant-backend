from datetime import datetime

from sqlalchemy import String, Text, Float, Integer, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ProjectAnalysis(Base):
    """Project-wide analysis, one row per project (not per file)."""

    __tablename__ = "project_analyses"

    project_analysis_id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.project_id"), nullable=False, unique=True)

    overview: Mapped[str] = mapped_column(Text, nullable=False)
    security_summary: Mapped[str] = mapped_column(Text, nullable=False)

    average_quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    average_security_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    average_complexity: Mapped[str | None] = mapped_column(String(20), nullable=True)

    total_files: Mapped[int] = mapped_column(Integer, nullable=False)
    files_with_analysis: Mapped[int] = mapped_column(Integer, nullable=False)
    files_with_security: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped["Project"] = relationship()