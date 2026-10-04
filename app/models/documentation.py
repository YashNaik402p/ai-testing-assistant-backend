from datetime import datetime

from sqlalchemy import Text, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Documentation(Base):
    """Maps to the Documentation class in the class diagram."""

    __tablename__ = "documentation"

    doc_id: Mapped[int] = mapped_column(primary_key=True, index=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("analysis_reports.report_id"), nullable=False, unique=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    report: Mapped["AnalysisReport"] = relationship(back_populates="documentation")
