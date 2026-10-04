from sqlalchemy import String, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TestCase(Base):
    """Maps to the TestCase class in the class diagram."""

    __tablename__ = "test_cases"

    test_case_id: Mapped[int] = mapped_column(primary_key=True, index=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("analysis_reports.report_id"), nullable=False)
    test_code: Mapped[str] = mapped_column(String(20), nullable=False)  # e.g. "TC001"
    test_type: Mapped[str] = mapped_column(String(50), nullable=False)  # Positive/Negative/Boundary/Edge/Security
    description: Mapped[str] = mapped_column(Text, nullable=False)
    expected_result: Mapped[str] = mapped_column(Text, nullable=False)

    report: Mapped["AnalysisReport"] = relationship(back_populates="test_cases")