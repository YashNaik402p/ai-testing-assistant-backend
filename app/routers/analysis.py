from fastapi import APIRouter, Depends, HTTPException,Query,status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.project import Project
from app.models.source_code import SourceCode
from app.models.analysis_report import AnalysisReport
from app.models.test_case import TestCase
from app.models.security_analysis import SecurityAnalysis
from app.models.documentation import Documentation
from app.schemas.documentation import DocumentationOut
from app.schemas.security_analysis import SecurityAnalysisOut
from app.schemas.analysis_report import AnalysisReportOut
from app.schemas.test_case import TestCaseOut
from app.core.deps import get_current_user
from app.services.ai_engine import analyze_code, generate_test_cases,analyze_security, generate_documentation, AIEngineError
#========================================================
#Download doc imports

from app.routers.download_documentation import download_pdf
import io
import json
import re
from xml.sax.saxutils import escape
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from openpyxl.styles import Font, Alignment

from fastapi import Query, Depends, HTTPException
from sqlalchemy.orm import Session
#========================================================

router = APIRouter(prefix="/projects/{project_id}/source-code/{code_id}", tags=["analysis"])


def get_owned_source_code(project_id: int, code_id: int, db: Session, current_user: User) -> SourceCode:
    """
    Shared helper: fetch a specific source code entry, but only if its parent
    project belongs to the logged-in user. Two checks in one: project ownership,
    and that this code_id actually belongs to that project.
    """
    source = (
        db.query(SourceCode)
        .join(Project)
        .filter(
            SourceCode.code_id == code_id,
            SourceCode.project_id == project_id,
            Project.user_id == current_user.user_id,
        )
        .first()
    )
    if source is None:
        raise HTTPException(status_code=404, detail="Source code not found")
    return source

def get_owned_project(project_id: int, db: Session, current_user: User) -> Project:
    project = (
        db.query(Project)
        .filter(Project.project_id == project_id, Project.user_id == current_user.user_id)
        .first()
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

#====================================================================================================================================
# Analyze Source code
#====================================================================================================================================
@router.post("/analyze", response_model=AnalysisReportOut)
def analyze_source_code(
    project_id: int,
    code_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Run AI analysis on a piece of source code: detect complexity, quality score,
    and a plain-English explanation. Matches 'Analyze Code' + 'Generate Explanation'
    from the use case diagram.

    Running this again on the same code re-analyzes it and updates the existing
    report, rather than creating a duplicate.
    """
    source = get_owned_source_code(project_id, code_id, db, current_user)

    try:
        result = analyze_code(source.code_content, source.language)
    except AIEngineError as e:
        raise HTTPException(status_code=503, detail=str(e))

    # If this code was already analyzed before, update that report instead of
    # creating a second one — code_id is unique on AnalysisReport (one report per file).
    report = db.query(AnalysisReport).filter(AnalysisReport.code_id == code_id).first()

    if report is None:
        report = AnalysisReport(code_id=code_id)
        db.add(report)

    report.complexity = result["complexity"]
    report.quality_score = result["quality_score"]
    report.explanation_summary = result["explanation"]

    db.commit()
    db.refresh(report)

    return report

#====================================================================================================================================
# Get Analysis 
#====================================================================================================================================
@router.get("/report", response_model=AnalysisReportOut)
def get_analysis_report(
    project_id: int,
    code_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fetch the existing analysis report for a piece of source code, if one exists."""
    get_owned_source_code(project_id, code_id, db, current_user)  # ownership check

    report = db.query(AnalysisReport).filter(AnalysisReport.code_id == code_id).first()
    if report is None:
        raise HTTPException(status_code=404, detail="No analysis report yet — run /analyze first")

    return report

#====================================================================================================================================
# Generate test cases for code
#====================================================================================================================================
@router.post("/generate-test-cases", response_model=list[TestCaseOut])
def generate_test_cases_for_code(
    project_id: int,
    code_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate AI-based test cases for a piece of source code.
    Matches the 'Generate Test Cases' use case.

    Requires that /analyze has already been run — test cases attach to an
    AnalysisReport (report_id), not directly to the source code.

    Running this again replaces the old test cases with a freshly generated set,
    rather than piling up duplicates every time you regenerate.
    """
    source = get_owned_source_code(project_id, code_id, db, current_user)

    report = db.query(AnalysisReport).filter(AnalysisReport.code_id == code_id).first()
    if report is None:
        raise HTTPException(status_code=400, detail="Run /analyze on this code first, before generating test cases")

    try:
        generated = generate_test_cases(source.code_content, source.language)
    except AIEngineError as e:
        raise HTTPException(status_code=503, detail=str(e))

    # Clear out any previously generated test cases for this report, so re-running
    # this endpoint replaces them instead of endlessly appending duplicates.
    db.query(TestCase).filter(TestCase.report_id == report.report_id).delete()

    new_test_cases = []
    for index, item in enumerate(generated, start=1):
        test_case = TestCase(
            report_id=report.report_id,
            test_code=f"TC{index:03d}",  # TC001, TC002, ...
            test_type=item.get("test_type", "Unknown"),
            description=item["description"],
            expected_result=item["expected_result"],
        )
        db.add(test_case)
        new_test_cases.append(test_case)

    db.commit()
    for tc in new_test_cases:
        db.refresh(tc)

    return new_test_cases

#====================================================================================================================================
# Get test cases
#====================================================================================================================================
@router.get("/test-cases", response_model=list[TestCaseOut])
def list_test_cases(
    project_id: int,
    code_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List the generated test cases for a piece of source code."""
    get_owned_source_code(project_id, code_id, db, current_user)

    report = db.query(AnalysisReport).filter(AnalysisReport.code_id == code_id).first()
    if report is None:
        return []  # no analysis run yet, so no test cases either

    return db.query(TestCase).filter(TestCase.report_id == report.report_id).all()

#====================================================================================================================================
# Security analysis
#====================================================================================================================================
@router.post("/analyze-security", response_model=SecurityAnalysisOut)
def analyze_security_for_code(
    project_id: int,
    code_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Run AI security analysis on a piece of source code.
    Requires that /analyze has already been run.
    Running this again UPDATES the existing security analysis rather than duplicating.
    """
    source = get_owned_source_code(project_id, code_id, db, current_user)

    report = db.query(AnalysisReport).filter(AnalysisReport.code_id == code_id).first()
    if report is None:
        raise HTTPException(status_code=400, detail="Run /analyze on this code first, before running security analysis")

    try:
        result = analyze_security(source.code_content, source.language)
    except AIEngineError as e:
        raise HTTPException(status_code=503, detail=str(e))

    security = db.query(SecurityAnalysis).filter(SecurityAnalysis.report_id == report.report_id).first()

    if security is None:
        security = SecurityAnalysis(report_id=report.report_id)
        db.add(security)

    security.issue_description = result["issue_description"]
    security.severity = result["severity"]
    security.recommendation = result["recommendation"]
    security.security_score = result["security_score"]

    db.commit()
    db.refresh(security)

    return security

#====================================================================================================================================
# Get Security analysis
#====================================================================================================================================
@router.get("/security-report", response_model=SecurityAnalysisOut)
def get_security_report(
    project_id: int,
    code_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fetch the existing security analysis for a piece of source code, if one exists."""
    get_owned_source_code(project_id, code_id, db, current_user)

    report = db.query(AnalysisReport).filter(AnalysisReport.code_id == code_id).first()
    if report is None:
        raise HTTPException(status_code=404, detail="No analysis report yet — run /analyze first")

    security = db.query(SecurityAnalysis).filter(SecurityAnalysis.report_id == report.report_id).first()
    if security is None:
        raise HTTPException(status_code=404, detail="No security analysis yet — run /analyze-security first")

    return security
#====================================================================================================================================
# Generate Doc
#====================================================================================================================================
@router.post("/generate-documentation", response_model=DocumentationOut)
def generate_documentation_for_code(
    project_id: int,
    code_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generate AI-based documentation for a piece of source code.
    Requires that /analyze has already been run.
    Running this again UPDATES the existing documentation rather than duplicating.
    """
    source = get_owned_source_code(project_id, code_id, db, current_user)

    report = db.query(AnalysisReport).filter(AnalysisReport.code_id == code_id).first()
    if report is None:
        raise HTTPException(status_code=400, detail="Run /analyze on this code first, before generating documentation")

    try:
        content = generate_documentation(source.code_content, source.language)
    except AIEngineError as e:
        raise HTTPException(status_code=503, detail=str(e))

    doc = db.query(Documentation).filter(Documentation.report_id == report.report_id).first()

    if doc is None:
        doc = Documentation(report_id=report.report_id, content=content)
        db.add(doc)
    else:
        doc.content = content

    db.commit()
    db.refresh(doc)

    return doc

#====================================================================================================================================
# Get doc
#====================================================================================================================================
@router.get("/documentation", response_model=DocumentationOut)
def get_documentation(
    project_id: int,
    code_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fetch the existing documentation for a piece of source code, if one exists."""
    get_owned_source_code(project_id, code_id, db, current_user)

    report = db.query(AnalysisReport).filter(AnalysisReport.code_id == code_id).first()
    if report is None:
        raise HTTPException(status_code=404, detail="No analysis report yet — run /analyze first")

    doc = db.query(Documentation).filter(Documentation.report_id == report.report_id).first()
    if doc is None:
        raise HTTPException(status_code=404, detail="No documentation yet — run /generate-documentation first")

    return doc

#================================================================================================================
# Download Documnetation...
#================================================================================================================

@router.get("/documentation/download")
def download_documentation(
    project_id: int,
    code_id: int,
    format: str = Query(..., pattern="^(pdf|json)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Download generated documentation as PDF, Excel, or JSON.

    Supported formats:
    - pdf
    - json
    """

    # ---------------------------------------------------------
    # Step 1: Check source code belongs to logged-in user
    # ---------------------------------------------------------
    source = get_owned_source_code(
        project_id,
        code_id,
        db,
        current_user
    )
    project = get_owned_project(project_id, db, current_user)
    
    # ---------------------------------------------------------
    # Step 2: Find analysis report
    # ---------------------------------------------------------
    report = (
        db.query(AnalysisReport)
        .filter(AnalysisReport.code_id == code_id)
        .first()
    )

    if report is None:
        raise HTTPException(
            status_code=404,
            detail="No analysis report found. Run /analyze first."
        )

    # ---------------------------------------------------------
    # Step 3: Find documentation
    # ---------------------------------------------------------
    doc = (
        db.query(Documentation)
        .filter(Documentation.report_id == report.report_id)
        .first()
    )

    if doc is None:
        raise HTTPException(
            status_code=404,
            detail="No documentation found. Run /generate-documentation first."
        )

    # =========================================================
    # JSON
    # =========================================================
    if format == "json":
        data = {
            "title":project.project_name,
            "file_name": source.file_name,
            "language": source.language,
            "documentation": doc.content,
        }

        json_data = json.dumps(
            data,
            indent=4,
            ensure_ascii=False
        )

        return StreamingResponse(
            io.BytesIO(json_data.encode("utf-8")),
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="{source.file_name}_documentation.json"'
            },
        )

    
    # =========================================================
    # PDF
    # =========================================================
    elif format == "pdf":
        file_info_flag=True
        return download_pdf(
        project,
        doc,file_info_flag,
        source
    )
