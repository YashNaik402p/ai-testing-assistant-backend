import json
from fastapi import APIRouter, Depends, HTTPException,Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from fpdf import FPDF
from app.database import get_db
from app.models.user import User
from app.models.project import Project
from app.models.source_code import SourceCode
from app.models.analysis_report import AnalysisReport
from app.models.security_analysis import SecurityAnalysis
from app.models.project_analysis import ProjectAnalysis
from app.schemas.project_analysis import ProjectAnalysisOut
from app.core.deps import get_current_user
from app.services.ai_engine import analyze_project_overview, AIEngineError, generate_project_documentation
from app.models.project_documentation import ProjectDocumentation
from app.schemas.project_documentation import ProjectDocumentationOut
from app.routers.download_documentation import download_pdf

router = APIRouter(prefix="/projects/{project_id}", tags=["project-analysis"])

COMPLEXITY_TO_NUMBER = {"Low": 1, "Medium": 2, "High": 3}
NUMBER_TO_COMPLEXITY = {1: "Low", 2: "Medium", 3: "High"}


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
# Analyse project
#====================================================================================================================================
@router.post("/analyze-project", response_model=ProjectAnalysisOut)
def analyze_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_owned_project(project_id, db, current_user)

    source_codes = db.query(SourceCode).filter(SourceCode.project_id == project_id).all()
    if not source_codes:
        raise HTTPException(status_code=400, detail="Upload at least one file before analyzing the project")

    quality_scores = []
    complexity_numbers = []
    security_scores = []
    file_analyses = []
    file_securities = []

    for source in source_codes:
        report = db.query(AnalysisReport).filter(AnalysisReport.code_id == source.code_id).first()

        if report is not None:
            if report.quality_score is not None:
                quality_scores.append(report.quality_score)
            if report.complexity in COMPLEXITY_TO_NUMBER:
                complexity_numbers.append(COMPLEXITY_TO_NUMBER[report.complexity])
            if report.explanation_summary:
                file_analyses.append({"file_name": source.file_name, "explanation_summary": report.explanation_summary})

            security = db.query(SecurityAnalysis).filter(SecurityAnalysis.report_id == report.report_id).first()
            if security is not None:
                security_scores.append(security.security_score)
                file_securities.append({
                    "file_name": source.file_name,
                    "issue_description": security.issue_description,
                    "severity": security.severity,
                    "recommendation": security.recommendation,
                })

    if not quality_scores and not security_scores:
        raise HTTPException(
            status_code=400,
            detail="Run /analyze (and ideally /analyze-security) on at least one file before analyzing the overall project",
        )

    try:
        result = analyze_project_overview(file_analyses, file_securities)
    except AIEngineError as e:
        raise HTTPException(status_code=503, detail=str(e))

    average_quality = sum(quality_scores) / len(quality_scores) if quality_scores else None
    average_security = sum(security_scores) / len(security_scores) if security_scores else None
    average_complexity = None
    if complexity_numbers:
        rounded = round(sum(complexity_numbers) / len(complexity_numbers))
        rounded = max(1, min(3, rounded))
        average_complexity = NUMBER_TO_COMPLEXITY[rounded]

    project_analysis = db.query(ProjectAnalysis).filter(ProjectAnalysis.project_id == project_id).first()
    if project_analysis is None:
        project_analysis = ProjectAnalysis(project_id=project_id)
        db.add(project_analysis)

    project_analysis.overview = result["overview"]
    project_analysis.security_summary = result["security_summary"]
    project_analysis.average_quality_score = average_quality
    project_analysis.average_security_score = average_security
    project_analysis.average_complexity = average_complexity
    project_analysis.total_files = len(source_codes)
    project_analysis.files_with_analysis = len(quality_scores)
    project_analysis.files_with_security = len(security_scores)

    db.commit()
    db.refresh(project_analysis)

    return project_analysis

#====================================================================================================================================
# Project Report
#====================================================================================================================================
@router.get("/project-report", response_model=ProjectAnalysisOut)
def get_project_report(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_owned_project(project_id, db, current_user)
    project_analysis = db.query(ProjectAnalysis).filter(ProjectAnalysis.project_id == project_id).first()
    if project_analysis is None:
        raise HTTPException(status_code=404, detail="No project analysis yet — run /analyze-project first")
    return project_analysis
#====================================================================================================================================
# Project documentation
#====================================================================================================================================
@router.post("/generate-documentation", response_model=ProjectDocumentationOut)
def generate_project_documentation_endpoint(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Requires /analyze-project to have already been run."""
    get_owned_project(project_id, db, current_user)

    project_analysis = db.query(ProjectAnalysis).filter(ProjectAnalysis.project_id == project_id).first()
    if project_analysis is None:
        raise HTTPException(status_code=400, detail="Run /analyze-project first, before generating project documentation")

    try:
        content = generate_project_documentation(
            overview=project_analysis.overview,
            security_summary=project_analysis.security_summary,
            average_quality_score=project_analysis.average_quality_score,
            average_security_score=project_analysis.average_security_score,
            average_complexity=project_analysis.average_complexity,
        )
    except AIEngineError as e:
        raise HTTPException(status_code=503, detail=str(e))

    doc = db.query(ProjectDocumentation).filter(ProjectDocumentation.project_id == project_id).first()
    if doc is None:
        doc = ProjectDocumentation(project_id=project_id, content=content)
        db.add(doc)
    else:
        doc.content = content

    db.commit()
    db.refresh(doc)

    return doc


@router.get("/documentation", response_model=ProjectDocumentationOut)
def get_project_documentation(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_owned_project(project_id, db, current_user)
    doc = db.query(ProjectDocumentation).filter(ProjectDocumentation.project_id == project_id).first()
    if doc is None:
        raise HTTPException(status_code=404, detail="No project documentation yet — run /generate-documentation first")
    return doc

#====================================================================================================================================
# Download Project Report
#====================================================================================================================================



@router.get("/download")
def download_project_report(
    project_id: int,
    file_format: str = Query(..., pattern="^(pdf|json)$", description="Either 'pdf' or 'json'"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download the project-level analysis as PDF or JSON. Matches 'Download Report'."""
    project = get_owned_project(project_id, db, current_user)

    project_analysis = db.query(ProjectAnalysis).filter(ProjectAnalysis.project_id == project_id).first()
    if project_analysis is None:
        raise HTTPException(status_code=404, detail="No project analysis yet — run /analyze-project first")
    doc = db.query(ProjectDocumentation).filter(ProjectDocumentation.project_id == project_id).first()
    if doc is None:
        raise HTTPException(status_code=404, detail="No project documentation yet — run /generate-documentation first")
    

    title = f"{project.project_name} document"

    if file_format == "json":
        data = {
            "title": title,
             "documentation": doc.content,
            "average_quality_score": round(project_analysis.average_quality_score),
            "average_security_score": round(project_analysis.average_security_score),
            "average_complexity": project_analysis.average_complexity,
            "total_files": project_analysis.total_files,
            "files_with_analysis": project_analysis.files_with_analysis,
            "files_with_security": project_analysis.files_with_security,
            "generated_at": project_analysis.created_at.isoformat(),
        }
        json_bytes = json.dumps(data, indent=2).encode("utf-8")
        return Response(
            content=json_bytes,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{title}.json"'},
        )
    else:
         file_info_flag=False
         return download_pdf(
                project,
                doc,file_info_flag   
            )