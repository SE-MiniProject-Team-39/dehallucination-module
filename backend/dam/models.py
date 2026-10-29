import os
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, Float, ForeignKey, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def now():
    return datetime.now(timezone.utc).isoformat()


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(20))


class ApiKey(Base):
    __tablename__ = "api_keys"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    key_hash: Mapped[str] = mapped_column(String(64), unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    key_id: Mapped[str | None] = mapped_column(ForeignKey("api_keys.id"), nullable=True)
    source_app_id: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[str] = mapped_column(String(40), default=now)
    text: Mapped[str] = mapped_column(Text)
    context: Mapped[str] = mapped_column(Text, default="")
    threshold: Mapped[float] = mapped_column(Float)
    approved_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
    report: Mapped[dict] = mapped_column(JSON)


class Audit(Base):
    __tablename__ = "audit"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[str] = mapped_column(String(40), default=now)
    actor: Mapped[str] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(80))
    details: Mapped[dict] = mapped_column(JSON)


class Config(Base):
    __tablename__ = "config"
    id: Mapped[str] = mapped_column(String(30), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)


class Cache(Base):
    __tablename__ = "claim_cache"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[str] = mapped_column(String(40), default=now)
    value: Mapped[dict] = mapped_column(JSON)


def database(url=None):
    url = url or os.getenv("DATABASE_URL", "sqlite:///./dam.db")
    options = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=options)
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)
