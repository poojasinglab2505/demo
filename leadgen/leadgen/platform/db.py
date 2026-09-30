import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        # Local dev fallback — a real deployment should set DATABASE_URL to Postgres.
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "platform.db")
        return f"sqlite:///{db_path}"
    # Some hosts (Railway, Render, Heroku-style) hand out "postgres://"; SQLAlchemy needs "postgresql://".
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


engine = create_engine(_database_url(), future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)


def init_db():
    from . import models  # noqa: F401 — ensures models are registered on Base before create_all

    Base.metadata.create_all(engine)
