from datetime import datetime

from sqlalchemy import String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SourceCode(Base):
    """Maps to the SourceCode class in the class diagram."""

    __tablename__ = "source_codes"

    code_id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.project_id"), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    code_content: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(50), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped["Project"] = relationship(back_populates="source_codes")

    # 1 SourceCode -> 1 AnalysisReport ("owns")
    analysis_report: Mapped["AnalysisReport | None"] = relationship(
        back_populates="source_code", cascade="all, delete-orphan", uselist=False
    )
