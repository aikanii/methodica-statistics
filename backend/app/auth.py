from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from .config import ACCESS_TOKEN_EXPIRE_MINUTES, ALGORITHM, SECRET_KEY
from .db import get_db
from .models import User
from .utils import new_id

GUEST_EMAIL = "guest@methodica.app"

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


def create_token(user_id: str, email: str) -> str:
    exp = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": user_id, "email": email, "exp": exp}, SECRET_KEY, algorithm=ALGORITHM)


def get_or_create_guest(db: Session) -> User:
    u = db.query(User).filter(User.email == GUEST_EMAIL).first()
    if u:
        return u
    u = User(
        id=new_id(),
        email=GUEST_EMAIL,
        name="You",
        password_hash=hash_password("guest-local"),
        role="analyst",
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    """Auth is optional — unauthenticated requests use a local guest workspace."""
    if creds is None:
        return get_or_create_guest(db)
    try:
        payload = jwt.decode(creds.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        uid = payload.get("sub")
    except JWTError:
        return get_or_create_guest(db)
    user = db.query(User).filter(User.id == uid).first()
    return user or get_or_create_guest(db)
