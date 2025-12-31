"""
Database Initialization Script
==============================
Creates all tables and enables the pgvector extension.
"""

import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.database.models import Base


def get_database_url() -> str:
    """Get database URL from environment or use default."""
    return os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/logos"
    )


def init_database(echo: bool = False) -> None:
    """
    Initialize the database:
    1. Enable pgvector extension
    2. Create all tables
    """
    database_url = get_database_url()
    engine = create_engine(database_url, echo=echo)
    
    # Enable pgvector extension
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
        print("✓ pgvector extension enabled")
    
    # Create all tables
    Base.metadata.create_all(engine)
    print("✓ All tables created")
    
    # Print summary
    print("\nCreated tables:")
    for table_name in Base.metadata.tables.keys():
        print(f"  - {table_name}")
    
    return engine


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
