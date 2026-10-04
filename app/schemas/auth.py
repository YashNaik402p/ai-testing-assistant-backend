from datetime import datetime
from pydantic import BaseModel, EmailStr


class UserRegister(BaseModel):
    """What the client sends us when registering a new user."""
    name: str
    email: EmailStr
    password: str  # plain text, only for this one request — we hash it immediately


class UserLogin(BaseModel):
    """What the client sends us when logging in."""
    email: EmailStr
    password: str


class UserOut(BaseModel):
    """What we send back to the client. Notice: no password_hash here — ever."""
    user_id: int
    name: str
    email: EmailStr
    role: str
    created_at: datetime

    class Config:
        from_attributes = True  # lets us build this directly from a User DB object


class Token(BaseModel):
    """What we send back after a successful login."""
    access_token: str
    token_type: str = "bearer"
