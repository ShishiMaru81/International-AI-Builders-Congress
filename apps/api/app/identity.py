"""Shared opaque-token identity and explicit, safe user serialization."""
import hashlib
from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .db import Token, User, get_db


def user_view(user: User) -> dict:
    return dict(id=user.id, name=user.name, email=user.email, role=user.role,
                preferences=user.preferences or {}, is_active=user.is_active)


def optional_user(db: Session = Depends(get_db), authorization: str | None = Header(default=None)) -> User | None:
    if authorization is None:
        return None
    scheme, _, raw = authorization.partition(' ')
    if scheme.lower() != 'bearer' or not raw or len(raw) > 512:
        raise HTTPException(401, 'Sign in first', headers={'WWW-Authenticate': 'Bearer'})
    token = db.get(Token, hashlib.sha256(raw.encode()).hexdigest())
    try:
        expires = datetime.fromisoformat(token.expires) if token else None
        valid = expires is not None and expires.tzinfo is not None and expires > datetime.now(timezone.utc)
    except (ValueError, TypeError):
        valid = False
    user = db.get(User, token.user_id) if valid else None
    if not user or not user.is_active:
        raise HTTPException(401, 'Session expired', headers={'WWW-Authenticate': 'Bearer'})
    return user


def require_user(db: Session = Depends(get_db), authorization: str | None = Header(default=None)) -> User:
    user = optional_user(db, authorization)
    if user is None:
        raise HTTPException(401, 'Sign in first', headers={'WWW-Authenticate': 'Bearer'})
    return user
