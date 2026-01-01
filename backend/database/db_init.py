"""
Database Initialization Script
==============================
Creates all tables and enables the pgvector extension.
"""

import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend.database.models import Base


def get_database_url() -> str:
    """Get database URL from environment or use default.
    
    Prefers SQLALCHEMY_DATABASE_URL (for psycopg driver) over DATABASE_URL
    (which Chainlit uses with asyncpg and requires plain postgresql://).
    """
    return os.getenv(
        "SQLALCHEMY_DATABASE_URL",
        os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://postgres:postgres@postgres:5432/logos"
        )
    )


def init_database(echo: bool = False) -> None:
    """
    [DEPRECATED] Use Alembic for migrations.
    Legacy function that formerly initialized the database.
    """
    print("WARNING: init_database() is deprecated. Please use 'alembic upgrade head' to manage schemas.")
    database_url = get_database_url()
    return create_engine(database_url, echo=echo)


def get_session(engine=None):
    """Create a new database session."""
    if engine is None:
        engine = create_engine(get_database_url())
    Session = sessionmaker(bind=engine)
    return Session()


if __name__ == "__main__":
    print("Initializing Logos database...\n")
    init_database(echo=False)
    print("\n✓ Database initialization complete!")
