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


def _migrate() -> None:
    """Add new columns to existing tables without dropping data.

    Safe to run on fresh installs (create_all already adds the column) and on
    existing installs where the column is absent.
    """
    from sqlalchemy import text

    with engine.connect() as conn:
        # Check whether the table exists at all first
        tables = {
            row[0]
            for row in conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            )
        }
        if "category_run_records" not in tables:
            return  # create_all hasn't run yet or table was never created

        result = conn.execute(text("PRAGMA table_info(category_run_records)"))
        existing = {row[1] for row in result}
        if "scheduled_at" not in existing:
            conn.execute(
                text("ALTER TABLE category_run_records ADD COLUMN scheduled_at DATETIME")
            )
            conn.commit()


def init_db():
    # Ensure all models are imported so Base.metadata is complete
    import dashboard.db_models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _migrate()
