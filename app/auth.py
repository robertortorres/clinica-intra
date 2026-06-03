import os
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Request

SECRET_KEY = os.getenv("SECRET_KEY", "medsel-secret-2024")
ALGORITHM  = "HS256"
TOKEN_EXPIRE_HOURS = 10

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(p: str) -> str:
    return pwd_context.hash(p)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_token(data: dict) -> str:
    to_encode = data.copy()
    to_encode["exp"] = datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS)
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_user(request: Request) -> Optional[dict]:
    token = request.cookies.get("medsel_token")
    if not token:
        return None
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


def require_auth(request: Request) -> Optional[dict]:
    return get_user(request)
