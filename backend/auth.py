# auth.py
# Handles all authentication — PostgreSQL user store, JWT creation, token validation.

import os
from datetime import datetime, timedelta
from typing import Optional
import uuid

from fastapi import Depends, HTTPException, Header
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db, UserModel, init_db

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-this-in-production-please")
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ── Pydantic models ────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    email: str
    password: str

class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str

class TokenResponse(BaseModel):
    token: str
    user_id: str
    name: str

# ── Core auth functions ────────────────────────────────────────────────────
def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain[:72], hashed)

def create_token(user_id: str, email: str) -> str:
    payload = {
        "user_id": user_id,
        "email": email,
        "exp": datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token. Please log in again.")

# ── FastAPI dependencies ───────────────────────────────────────────────────
def get_current_user(authorization: str = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated. Please log in.")
    token = authorization.replace("Bearer ", "")
    return decode_token(token)

def get_optional_user(authorization: str = Header(default=None)) -> Optional[dict]:
    if not authorization:
        return None
    try:
        return get_current_user(authorization)
    except HTTPException:
        return None

# ── Route handlers ─────────────────────────────────────────────────────────
def login_handler(request: LoginRequest, db: Session) -> TokenResponse:
    user = db.query(UserModel).filter(UserModel.email == request.email).first()
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    token = create_token(user.user_id, user.email)
    return TokenResponse(token=token, user_id=user.user_id, name=user.name)

def register_handler(request: RegisterRequest, db: Session) -> TokenResponse:
    existing = db.query(UserModel).filter(UserModel.email == request.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered.")
    if len(request.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")

    user_id = f"usr_{uuid.uuid4().hex[:8]}"
    new_user = UserModel(
        user_id=user_id,
        email=request.email,
        name=request.name,
        hashed_password=pwd_context.hash(request.password[:72]),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    token = create_token(user_id, request.email)
    return TokenResponse(token=token, user_id=user_id, name=request.name)