from datetime import datetime

from sqlalchemy import String, Text, Float, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AnalysisReport(Base):
    """Maps to the AnalysisReport class in the class diagram."""

    __tablename__ = "analysis_reports"

    report_id: Mapped[int] = mapped_column(primary_key=True, index=True)
    code_id: Mapped[int] = mapped_column(ForeignKey("source_codes.code_id"), nullable=False, unique=True)
    explanation_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    complexity: Mapped[str | None] = mapped_column(String(20), nullable=True)  # "Low" | "Medium" | "High"
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    source_code: Mapped["SourceCode"] = relationship(back_populates="analysis_report")

    # 1 AnalysisReport -> * TestCase ("generates")
    test_cases: Mapped[list["TestCase"]] = relationship(back_populates="report", cascade="all, delete-orphan")

    # 1 AnalysisReport -> 1 SecurityAnalysis ("produces")
    security_analysis: Mapped["SecurityAnalysis | None"] = relationship(
        back_populates="report", cascade="all, delete-orphan", uselist=False
    )

    # 1 AnalysisReport -> 1 Documentation ("generates")
    documentation: Mapped["Documentation | None"] = relationship(
        back_populates="report", cascade="all, delete-orphan", uselist=False
    )
