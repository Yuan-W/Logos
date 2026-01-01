"""
Logos Resource Lifecycle Management
===================================
Centralized resource initialization (Singletons) for Gateway and UI.
"""
import os
from typing import Optional, Any
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool
from sqlalchemy.orm import Session

# Import with 'backend' prefix after rename
from backend.database.db_init import get_session
from backend.utils.agent_factory import AgentFactory

# Globals
FACTORY: Optional[AgentFactory] = None
LLM: Optional[ChatOpenAI] = None
DB_SESSION: Optional[Session] = None
DB_POOL: Optional[AsyncConnectionPool] = None

async def init_globals():
    """Initialize global resources if not already set."""
    global FACTORY, LLM, DB_SESSION, DB_POOL
    
    if FACTORY:
        return

    print("Initializing Logos Global Resources...")
    
    # 1. DB Session
    DB_SESSION = get_session()
    
    # 2. LLM
    LLM = ChatOpenAI(
        model="gemini-3-flash-preview",
        openai_api_key=os.getenv("OPENAI_API_KEY", "sk-litellm-master-key"),
        openai_api_base=os.getenv("LITELLM_URL", "http://litellm:4000/v1")
    )
    
    # 3. Checkpointer (uses asyncpg, needs plain postgresql:// scheme)
    # DATABASE_URL is now set to plain scheme in docker-compose for Chainlit/asyncpg
    postgres_uri = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@postgres:5432/logos")
    if postgres_uri:
        # Ensure we strip any +driver suffix if present
        normalized_uri = postgres_uri.replace("+psycopg", "").replace("+asyncpg", "")
        DB_POOL = AsyncConnectionPool(conninfo=normalized_uri, max_size=20)
        await DB_POOL.open()
        checkpointer = AsyncPostgresSaver(DB_POOL)
    else:
        checkpointer = None
        print("WARNING: No DATABASE_URL found. memory only.")
    
    # 4. Factory
    FACTORY = AgentFactory(llm=LLM, session=DB_SESSION, checkpointer=checkpointer)
    print("Logos Resources Ready.")

async def shutdown_globals():
    """Cleanup global resources."""
    global DB_SESSION, DB_POOL
    if DB_SESSION:
        DB_SESSION.close()
    if DB_POOL:
        await DB_POOL.close()

def get_agent_factory() -> AgentFactory:
    if not FACTORY:
        raise RuntimeError("Global resources not initialized. Call init_globals() first.")
    return FACTORY
