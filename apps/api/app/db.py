import os
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import create_engine, String, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

def uid(): return uuid4().hex
def now(): return datetime.now(timezone.utc).isoformat()
class Base(DeclarativeBase): pass
class User(Base):
    __tablename__ = 'users'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String)
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)
class Token(Base):
    __tablename__ = 'sessions'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    expires: Mapped[str] = mapped_column(String)
class Record(Base):
    """Versioned domain document; ownership and plot scope are relational columns."""
    __tablename__ = 'records'
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    kind: Mapped[str] = mapped_column(String, index=True)
    plot_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    created_at: Mapped[str] = mapped_column(String, default=now)
    payload: Mapped[dict] = mapped_column(JSON)
class Reading(Base):
    __tablename__ = 'sensor_readings'
    __table_args__ = (UniqueConstraint('device_id', 'event_id'),)
    id: Mapped[str] = mapped_column(String, primary_key=True, default=uid)
    device_id: Mapped[str] = mapped_column(ForeignKey('records.id'))
    event_id: Mapped[str] = mapped_column(String)
    payload: Mapped[dict] = mapped_column(JSON)

url = os.getenv('DATABASE_URL', 'sqlite:///./agrosphere.db')
if url.startswith('postgres://'):
    url='postgresql+psycopg://'+url[len('postgres://'):]
elif url.startswith('postgresql://'):
    url='postgresql+psycopg://'+url[len('postgresql://'):]
engine = create_engine(url, connect_args={'check_same_thread': False} if url.startswith('sqlite') else {})
Session = sessionmaker(engine, expire_on_commit=False)
def get_db():
    with Session() as db: yield db
