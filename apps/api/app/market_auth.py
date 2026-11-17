"""Password authentication for farmer/customer accounts; operators use market_admin."""
import hashlib
import hmac
import math
import re
import secrets
import threading
import time
from collections import OrderedDict, deque
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .db import Token, User, get_db
from .identity import user_view

router = APIRouter(prefix='/api/v1/auth', tags=['authentication'])


def normalize_email(value: str) -> str:
    value = value.strip().lower()
    if len(value) > 254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
        raise ValueError('Enter a valid email address')
    return value


def hash_password(password: str) -> str:
    if not 10 <= len(password) <= 1024:
        raise ValueError('Password must contain 10 to 1024 characters')
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1, dklen=32)
    return f'scrypt$16384$8$1${salt.hex()}${digest.hex()}'


def verify_password(password: str, encoded: str | None) -> bool:
    try:
        algorithm, n, r, p, salt, expected = (encoded or '').split('$')
        # Never let corrupted stored parameters trigger unbounded memory/CPU work.
        if (algorithm, n, r, p) != ('scrypt', '16384', '8', '1'):
            return False
        salt_bytes, digest = bytes.fromhex(salt), bytes.fromhex(expected)
        if len(salt_bytes) != 16 or len(digest) != 32:
            return False
        actual = hashlib.scrypt(password.encode(), salt=salt_bytes, n=16384, r=8, p=1, dklen=32)
        return hmac.compare_digest(actual, digest)
    except (ValueError, TypeError):
        return False


_DUMMY_HASH = hash_password(secrets.token_urlsafe(32))


class Credentials(BaseModel):
    model_config = ConfigDict(extra='forbid')
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=1024)

    @field_validator('email')
    @classmethod
    def email_valid(cls, value):
        return normalize_email(value)


class Registration(Credentials):
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=10, max_length=1024)
    role: Literal['farmer', 'customer']

    @field_validator('name')
    @classmethod
    def name_valid(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('Name is required')
        return value


class AuthLimiter:
    """Thread-safe, bounded per-process throttling; edge limits are needed across workers."""
    def __init__(self):
        self.entries = OrderedDict()
        self.lock = threading.Lock()

    def check(self, ip: str, email: str):
        current = time.monotonic()
        keys = [(('ip', ip), 60), (('identity', ip, email), 12)]
        with self.lock:
            for key, limit in keys:
                bucket = self.entries.setdefault(key, deque())
                while bucket and bucket[0] <= current - 60:
                    bucket.popleft()
                self.entries.move_to_end(key)
                if len(bucket) >= limit:
                    raise HTTPException(429, 'Too many authentication attempts', headers={'Retry-After': str(max(1, math.ceil(60 - current + bucket[0])))})
            for key, _ in keys:
                self.entries[key].append(current)
            while len(self.entries) > 4096:
                self.entries.popitem(last=False)


_LIMITER_INIT_LOCK = threading.Lock()


def limit_auth(request: Request, email: str):
    with _LIMITER_INIT_LOCK:
        if not hasattr(request.app.state, 'market_auth_limiter'):
            request.app.state.market_auth_limiter = AuthLimiter()
    # Forwarded headers are deliberately ignored; proxy trust belongs to the server config.
    request.app.state.market_auth_limiter.check(request.client.host if request.client else 'unknown', email)


def issue_session(db: Session, user: User) -> dict:
    raw = secrets.token_urlsafe(40)
    db.add(Token(id=hashlib.sha256(raw.encode()).hexdigest(), user_id=user.id,
                 expires=(datetime.now(timezone.utc) + timedelta(days=7)).isoformat()))
    return {'token': raw, 'user': user_view(user)}


@router.post('/register')
def register(body: Registration, request: Request, db: Session = Depends(get_db)):
    limit_auth(request, body.email)
    if db.scalar(select(User.id).where(User.email == body.email)):
        raise HTTPException(409, 'An account already uses this email')
    user = User(name=body.name, email=body.email, password_hash=hash_password(body.password),
                role=body.role, is_active=True,
                preferences={'language': 'en', 'theme': 'light', 'retraining_consent': False, 'selected_plot_id': None})
    try:
        db.add(user)
        db.flush()
        response = issue_session(db, user)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'An account already uses this email') from None
    return response


@router.post('/login')
def login(body: Credentials, request: Request, db: Session = Depends(get_db)):
    limit_auth(request, body.email)
    user = db.scalar(select(User).where(User.email == body.email))
    valid = verify_password(body.password, user.password_hash if user and user.password_hash else _DUMMY_HASH)
    if not valid or not user or not user.password_hash or not user.is_active:
        raise HTTPException(401, 'Invalid email or password', headers={'WWW-Authenticate': 'Bearer'})
    response = issue_session(db, user)
    db.commit()
    return response
