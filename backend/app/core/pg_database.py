"""
PostgreSQL / SQLAlchemy setup.

Provides:
    engine       - SQLAlchemy engine bound to the DATABASE_URL.
    SessionLocal - session factory (non-async, autocommit off).
    Base         - declarative base for ORM models.
    get_db()     - FastAPI dependency that yields a session per request.
    init_db()    - creates all tables (safe to call repeatedly).
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from typing import Generator

from backend.app.core.config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,       # verify connections before checkout
    pool_size=5,               # fine for ≤100 users
    max_overflow=10,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yields a DB session, auto-closes after request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables that don't exist yet (idempotent)."""
    # Import models so Base.metadata knows about them
    import backend.app.models.sql_models  # noqa: F401
    Base.metadata.create_all(bind=engine)
