from datetime import datetime

from sqlalchemy import Text, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ProjectDocumentation(Base):
    """Project-wide documentation, one row per project. Built from ProjectAnalysis's
    already-computed fields (overview, security summary, averages) — not raw code."""

    __tablename__ = "project_documentation"

    project_documentation_id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.project_id"), nullable=False, unique=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped["Project"] = relationship()