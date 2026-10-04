import io
import zipfile
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File,status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.project import Project
from app.models.source_code import SourceCode
from app.schemas.source_code import SourceCodeCreate, SourceCodeOut
from app.core.deps import get_current_user

router = APIRouter(prefix="/projects/{project_id}/source-code", tags=["source-code"])

# Recognized plain-text code file extensions -> a human-readable language name.
# Used to auto-detect the language when a file is uploaded (instead of asking the user to type it).
LANGUAGE_BY_EXTENSION = {
    "py": "Python",
    "java": "Java",
    "js": "JavaScript",
    "ts": "TypeScript",
    "cpp": "C++",
    "c": "C",
    "cs": "C#",
    "rb": "Ruby",
    "go": "Go",
    "php": "PHP",
    "html": "html",
    "css": "css"
}
IGNORED_NAMES = {".DS_Store"}
SKIPPED_FOLDER_NAMES = {"site-packages", "__pycache__", ".git", "migrations"}

def _extension_for(language: str) -> str:
    """Pick a sensible file extension for auto-generated names, based on the language."""
    language_lower = language.lower()
    if "python" in language_lower or "fastapi" in language_lower or "flask" in language_lower:
        return "py"
    if "javascript" in language_lower:
        return "js"
    return "txt"  # safe fallback for anything we don't recognize


def get_owned_project(project_id: int, db: Session, current_user: User) -> Project:
    """
    Shared helper: fetch a project, but only if it belongs to the logged-in user.
    Used by every endpoint in this file, since they all act "inside" a specific project.
    """
    project = (
        db.query(Project)
        .filter(Project.project_id == project_id, Project.user_id == current_user.user_id)
        .first()
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("", response_model=SourceCodeOut, status_code=201)
def upload_source_code(
    project_id: int,
    payload: SourceCodeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Save source code (uploaded or pasted) into a project.
    Matches the 'Upload / Paste Source Code' use case.
    """
    # Step 1: make sure this project exists and belongs to the current user
    get_owned_project(project_id, db, current_user)

    # Step 2: if the user pasted code without a file name, generate a simple placeholder
    file_name = payload.file_name or f"pasted_code.{_extension_for(payload.language)}"

    # Step 3: save the code
    new_code = SourceCode(
        project_id=project_id,
        file_name=file_name,
        code_content=payload.code_content,
        language=payload.language,
    )

    db.add(new_code)
    db.commit()
    db.refresh(new_code)

    return new_code


@router.post("/upload-file", response_model=SourceCodeOut, status_code=201)
async def upload_source_file(
    project_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Save source code from an actual uploaded file (e.g. login.py).
    This is the "Upload" half of the use case — upload_source_code (above) is the "Paste" half.
    Only plain-text code files are supported (.py, .java, .js, etc.) — not PDFs, Word docs, or images.
    """
    # Step 1: make sure this project exists and belongs to the current user
    get_owned_project(project_id, db, current_user)

    # Step 2: figure out the language from the file's extension, e.g. "login.py" -> "py" -> "Python"
    extension = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    language = LANGUAGE_BY_EXTENSION.get(extension)

    if language is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '.{extension}'. Supported: {', '.join(LANGUAGE_BY_EXTENSION)}",
        )

    # Step 3: read the file's contents as plain text
    raw_bytes = await file.read()
    code_text = raw_bytes.decode("utf-8", errors="replace")  # "replace" avoids a crash on odd characters

    # Step 4: save it, exactly like the paste endpoint does
    new_code = SourceCode(
        project_id=project_id,
        file_name=file.filename,
        code_content=code_text,
        language=language,
    )

    db.add(new_code)
    db.commit()
    db.refresh(new_code)

    return new_code


@router.post("/upload-zip", response_model=list[SourceCodeOut], status_code=201)
async def upload_source_zip(
    project_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a .zip of a whole project folder (multiple files/subfolders).
    Only recognized code file extensions are kept — everything else (README,
    .txt notes, images, __MACOSX/ junk, .DS_Store) is silently skipped.
    Flask/Alembic migration files (migrations/env.py, migrations/versions/*.py)
    are also skipped, since they're generated boilerplate rather than app code.
    Each valid code file becomes its own SourceCode row, with file_name storing
    the path relative to the project root (e.g. "app/routes.py").
    """
    get_owned_project(project_id, db, current_user)
    raw_bytes = await file.read()

    try:
        zip_file = zipfile.ZipFile(io.BytesIO(raw_bytes))
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="That file isn't a valid .zip archive")

    all_names = [n for n in zip_file.namelist() if not n.endswith("/") and "__MACOSX" not in n]

    # If the whole zip is wrapped in a single top-level folder (very common when
    # zipping a project directory), strip that wrapper so paths start at the
    # project root instead of e.g. "Backend (Flask)/app/routes.py".
    top_level_dirs = {n.split("/", 1)[0] for n in all_names if "/" in n}
    common_root_prefix = f"{top_level_dirs.pop()}/" if len(top_level_dirs) == 1 else None

    created_entries = []

    for entry_name in zip_file.namelist():
        if entry_name.endswith("/"):
            continue
        if "__MACOSX" in entry_name:
            continue

        relative_path = entry_name.replace("\\", "/")
        if common_root_prefix and relative_path.startswith(common_root_prefix):
            relative_path = relative_path[len(common_root_prefix):]

        if not relative_path:
            continue

        path_parts = relative_path.split("/")
        base_name = path_parts[-1]

        if base_name in IGNORED_NAMES or base_name.startswith("."):
            continue

        # Skip Alembic/Flask migration files: migrations/env.py and
        # everything under migrations/versions/.
        if SKIPPED_FOLDER_NAMES & set(path_parts[:-1]):
            continue

        extension = base_name.rsplit(".", 1)[-1].lower() if "." in base_name else ""
        language = LANGUAGE_BY_EXTENSION.get(extension)
        if language is None:
            continue

        code_text = zip_file.read(entry_name).decode("utf-8", errors="replace")
        new_code = SourceCode(
            project_id=project_id,
            file_name=relative_path,
            code_content=code_text,
            language=language,
        )
        db.add(new_code)
        created_entries.append(new_code)

    if not created_entries:
        raise HTTPException(status_code=400, detail="No recognized code files found in this zip")

    db.commit()
    for entry in created_entries:
        db.refresh(entry)

    return created_entries
#==============================
@router.get("", response_model=list[SourceCodeOut])
def list_source_code(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List every source code file uploaded to this project."""
    get_owned_project(project_id, db, current_user)
    return db.query(SourceCode).filter(SourceCode.project_id == project_id).all()

