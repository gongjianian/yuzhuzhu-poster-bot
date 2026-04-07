from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from dashboard.config import settings


class Base(DeclarativeBase):
    pass


def get_engine():
    db_path = Path(settings.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{db_path}", echo=False)


engine = get_engine()
SessionLocal = sessionmaker(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
