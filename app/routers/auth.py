from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.auth import UserRegister, UserLogin, UserOut, Token
from app.core.security import hash_password, verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])

#====================================================================================================================================
# Register User
#====================================================================================================================================
@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    """Create a new user account. Matches the 'User Login / Register' use case."""

    # Step 1: make sure this email isn't already taken
    existing_user = db.query(User).filter(User.email == payload.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Step 2: hash the password — we never store what the user typed
    new_user = User(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role="user",
    )

    # Step 3: save to the database
    db.add(new_user)
    db.commit()
    db.refresh(new_user)  # loads the auto-generated user_id and created_at

    return new_user

#====================================================================================================================================
# Login User
#====================================================================================================================================
@router.post("/login", response_model=Token)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    """
    Verify credentials and issue a JWT.
    Matches steps 1-5 of the sequence diagram: verify credentials -> return JWT token.
    """

    user = db.query(User).filter(User.email == payload.email).first()

    # Deliberately the same error for "no such user" and "wrong password" —
    # this stops attackers from figuring out which emails are registered.
    invalid_credentials_error = HTTPException(status_code=401, detail="Invalid email or password")

    if user is None:
        raise invalid_credentials_error

    if not verify_password(payload.password, user.password_hash):
        raise invalid_credentials_error

    token = create_access_token(user_id=user.user_id)
    return Token(access_token=token)
