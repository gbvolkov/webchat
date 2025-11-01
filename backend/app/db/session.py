from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine

from app.core.config import get_settings

settings = get_settings()

engine = create_engine(settings.database_url, echo=False)


def init_db() -> None:
    """Create database tables."""
    from app.db import models  # noqa: F401 - ensure models are imported

    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    """FastAPI dependency that provides a database session."""
    with Session(engine) as session:
        yield session
