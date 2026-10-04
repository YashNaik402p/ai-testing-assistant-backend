from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.project import Project
from app.models.chat_message import ChatMessage
from app.schemas.chat_message import ChatMessageCreate, ChatMessageOut
from app.core.deps import get_current_user
from app.services.ai_engine import chat_with_ai, AIEngineError

router = APIRouter(prefix="/projects/{project_id}/chat", tags=["chat"])

MAX_HISTORY_MESSAGES = 10  # cap how much history we resend each time, so requests don't grow forever


def get_owned_project(project_id: int, db: Session, current_user: User) -> Project:
    project = (
        db.query(Project)
        .filter(Project.project_id == project_id, Project.user_id == current_user.user_id)
        .first()
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("", response_model=ChatMessageOut, status_code=201)
def send_chat_message(
    project_id: int,
    payload: ChatMessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Send a message to the AI assistant about this project, and get a reply.
    Earlier messages in this project's chat are included as context, so this
    is a real conversation, not an isolated one-off question each time.
    """
    get_owned_project(project_id, db, current_user)

    past_messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.project_id == project_id)
        .order_by(ChatMessage.timestamp.desc())
        .limit(MAX_HISTORY_MESSAGES)
        .all()
    )
    past_messages.reverse()

    history = []
    for past in past_messages:
        history.append({"role": "user", "content": past.message})
        if past.ai_response:
            history.append({"role": "assistant", "content": past.ai_response})

    try:
        ai_response = chat_with_ai(history, payload.message)
    except AIEngineError as e:
        raise HTTPException(status_code=503, detail=str(e))

    chat_message = ChatMessage(
        user_id=current_user.user_id,
        project_id=project_id,
        message=payload.message,
        ai_response=ai_response,
    )
    db.add(chat_message)
    db.commit()
    db.refresh(chat_message)

    return chat_message


@router.get("", response_model=list[ChatMessageOut])
def get_chat_history(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List the full chat history for this project, oldest first."""
    get_owned_project(project_id, db, current_user)
    return (
        db.query(ChatMessage)
        .filter(ChatMessage.project_id == project_id)
        .order_by(ChatMessage.timestamp.asc())
        .all()
    )