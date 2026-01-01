"""
Database Initialization Script
==============================
Creates all tables and enables the pgvector extension.
"""

import os
from typing import Optional

from sqlalchemy import create_engine, text, Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool

from backend.database.models import Base


# P2 Fix: Global engine singleton for connection pooling
_ENGINE: Optional[Engine] = None


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


def get_engine() -> Engine:
    """
    Get or create the global SQLAlchemy engine with connection pooling.
    
    P2 Fix: Uses QueuePool with configurable pool_size to prevent
    connection leaks under concurrent access.
    """
    global _ENGINE
    
    if _ENGINE is None:
        _ENGINE = create_engine(
            get_database_url(),
            poolclass=QueuePool,
            pool_size=10,        # Default concurrent connections
            max_overflow=20,     # Burst capacity
            pool_pre_ping=True,  # Verify connections before use
            pool_recycle=3600,   # Recycle connections after 1 hour
        )
    
    return _ENGINE


def init_database(echo: bool = False) -> None:
    """
    [DEPRECATED] Use Alembic for migrations.
    Legacy function that formerly initialized the database.
    """
    print("WARNING: init_database() is deprecated. Please use 'alembic upgrade head' to manage schemas.")
    database_url = get_database_url()
    return create_engine(database_url, echo=echo)


def get_session(engine: Optional[Engine] = None) -> Session:
    """
    Create a new database session using the pooled engine.
    
    Args:
        engine: Optional override engine. If None, uses the global pooled engine.
    
    Returns:
        A new SQLAlchemy Session instance.
    """
    if engine is None:
        engine = get_engine()
    SessionFactory = sessionmaker(bind=engine)
    return SessionFactory()


if __name__ == "__main__":
    print("Initializing Logos database...\n")
    init_database(echo=False)
    print("\n✓ Database initialization complete!")
