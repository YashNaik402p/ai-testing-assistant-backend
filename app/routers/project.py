from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectOut
from app.core.deps import get_current_user

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new project for the logged-in user.
    Matches the 'Create Project' use case, and steps 7-11 of the sequence diagram.

    Depends(get_current_user) is what makes this a protected route:
    FastAPI runs it before this function, using the JWT sent by the client.
    If the token is missing/invalid, the request is rejected before we even
    get here — current_user is guaranteed to be a real, logged-in User.
    """
    new_project = Project(
        user_id=current_user.user_id,  # we take this from the token, not from the request body
        project_name=payload.project_name,
        description=payload.description,
        language=payload.language,
    )

    db.add(new_project)
    db.commit()
    db.refresh(new_project)

    return new_project


@router.get("", response_model=list[ProjectOut])
def list_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all projects belonging to the logged-in user. Powers the Dashboard view."""
    return db.query(Project).filter(Project.user_id == current_user.user_id).all()


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fetch one specific project, but only if it belongs to the logged-in user."""
    project = (
        db.query(Project)
        .filter(Project.project_id == project_id, Project.user_id == current_user.user_id)
        .first()
    )

    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    return project

@router.put("/{project_id}", response_model=ProjectOut)
def update_project(payload: ProjectCreate,
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    
):
    project_to_update=get_project(project_id,db,current_user)
     
    project_to_update.project_name=payload.project_name
    project_to_update.description=payload.description
    project_to_update.language=payload.language
    db.commit()
    db.refresh(project_to_update)
    return project_to_update



@router.delete("/{project_id}")
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fetch one specific project, but only if it belongs to the logged-in user."""
    project = (
        db.query(Project)
        .filter(Project.project_id == project_id, Project.user_id == current_user.user_id)
        .first()
    )

    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    db.delete(project)
    db.commit()
    return {
        "message": "Project deleted successfully"
    }