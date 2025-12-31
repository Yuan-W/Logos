import asyncio
from psycopg import AsyncConnection
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
import os

POSTGRES_URI = "postgresql://postgres:postgres@localhost:5432/logos"

async def main():
    print("Initializing LangGraph Checkpoint tables...")
    
    # We use a raw connection to control autocommit for CREATE INDEX CONCURRENTLY
    async with await AsyncConnection.connect(POSTGRES_URI, autocommit=True) as conn:
        checkpointer = AsyncPostgresSaver(conn)
        await checkpointer.setup()
        
    print("✓ Checkpoint tables created via AsyncPostgresSaver.")

if __name__ == "__main__":
    asyncio.run(main())
