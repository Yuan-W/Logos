"""
Database Reset Script
=====================
DROPS ALL TABLES and re-creates them.
Use this when applying breaking schema changes (like Vector dimension changes).

WARNING: DATA LOSS!
"""
from sqlalchemy import create_engine
from backend.database.models import Base
from backend.database.db_init import get_database_url, init_database

def reset_database():
    print("⚠️  WARNING: This will DROP ALL DATA in the database.")
    print("Resetting database schema...")
    
    url = get_database_url()
    engine = create_engine(url)
    
    # Drop all tables
    Base.metadata.drop_all(engine)
    print("✓ All tables dropped.")
    
    # Re-init (Enable extension + Create tables)
    init_database()
    print("✅ Database reset complete. Schema updated.")

if __name__ == "__main__":
    confirm = input("Are you sure you want to delete all data? (y/N): ")
    if confirm.lower() == "y":
        reset_database()
    else:
        print("Cancelled.")
