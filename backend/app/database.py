"""Motor y sesion de SQLAlchemy (PostgreSQL)."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base declarativa de todos los modelos."""


def get_db() -> Generator[Session, None, None]:
    """Dependencia de FastAPI: una sesion por peticion."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
