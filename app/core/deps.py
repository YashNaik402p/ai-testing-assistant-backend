from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.security import decode_access_token
from app.models.user import User

# This tells FastAPI/Swagger: "just show a box to paste a raw Bearer token into"
bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Use this as a dependency on any endpoint that requires login, e.g.:

        @router.post("/projects")
        def create_project(..., current_user: User = Depends(get_current_user)):
            ...

    FastAPI automatically extracts the token from the request's Authorization header,
    runs this function, and hands you back a real User object (or rejects the request).
    """
    unauthorized_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = credentials.credentials  # the raw token string, without the "Bearer " prefix

    user_id = decode_access_token(token)
    if user_id is None:
        raise unauthorized_error

    user = db.get(User, user_id)
    if user is None:
        raise unauthorized_error

    return user
