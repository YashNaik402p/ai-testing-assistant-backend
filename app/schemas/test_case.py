from pydantic import BaseModel


class TestCaseOut(BaseModel):
    """One generated test case, as sent back to the client."""
    test_case_id: int
    report_id: int
    test_code: str          # e.g. "TC001"
    test_type: str          # e.g. "Positive", "Negative", "Boundary", "Security"
    description: str
    expected_result: str

    class Config:
        from_attributes = True
