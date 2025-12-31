"""
Logos API Gateway
=================
FastAPI server exposing multi-agent workflows.

Endpoints:
- POST /chat/{agent_role}: Routes to GM, Researcher, Coach, or Writer agents.

Supported Roles:
- gm (Dungeon Master)
- researcher (Deep Researcher)
- coach (Psychologist/Coach)
- writer (Novelist/Screenwriter)
"""

import os
from contextlib import asynccontextmanager
from typing import Dict, Any, List, Optional
from typing_extensions import TypedDict

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, BaseMessage
from langchain_core.messages.utils import convert_to_messages
from langchain_openai import ChatOpenAI
from langgraph.graph.state import CompiledStateGraph
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool
from sqlalchemy.orm import Session

from src.database.db_init import get_session
from src.agents.gm_agent import build_gm_agent
from src.agents.researcher_agent import build_researcher_agent
from src.agents.coach_agent import build_coach_agent
from src.agents.writer_agent import build_writer_agent


# =============================================================================
# Configuration & Globals
# =============================================================================

# Global Factory
FACTORY: Optional[Any] = None
LLM = None
DB_SESSION = None
DB_POOL = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize resources on startup."""
    global FACTORY, LLM, DB_SESSION, DB_POOL
    
    print("Initializing Logos Agents...")
    
    # 1. Setup DB Session (Global for prototype)
    DB_SESSION = get_session() 
    
    # 2. Setup LLM
    LLM = ChatOpenAI(
        model="gemini-3-flash-preview",
        openai_api_key=os.getenv("OPENAI_API_KEY", "sk-litellm-master-key"),
        openai_api_base=os.getenv("OPENAI_API_BASE_URL", "http://localhost:4000/v1")
    )
    
    # 3. Setup Postgres Checkpointer
    postgres_uri = "postgresql://postgres:postgres@localhost:5432/logos"
    DB_POOL = AsyncConnectionPool(conninfo=postgres_uri)
    await DB_POOL.open()
    checkpointer = AsyncPostgresSaver(DB_POOL)
    
    # 4. Initialize Agent Factory
    # We import here to avoid circular dependencies if any (though utils should be fine)
    from src.utils.agent_factory import AgentFactory
    FACTORY = AgentFactory(llm=LLM, session=DB_SESSION, checkpointer=checkpointer)
    
    print("Agent Factory Ready.")
    
    yield
    
    print("Shutting down...")
    DB_SESSION.close()
    await DB_POOL.close()


app = FastAPI(title="Logos AI OS", lifespan=lifespan)


# =============================================================================
# Models
# =============================================================================

class ChatRequest(BaseModel):
    user_id: str = Field(..., description="User identifier")
    query: str = Field(..., description="User input text")
    session_id: str = Field(..., description="Session/Thread ID for state isolation")
    
    # Optional fields for specific agents
    project_id: Optional[str] = Field(None, description="For Writer agent")
    role_mode: Optional[str] = Field(None, description="For Coach (psychologist/coach) or Writer")
    extra_context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional state fields")


class ChatResponse(BaseModel):
    response: str
    final_state: Dict[str, Any]


# =============================================================================
# Endpoints
# =============================================================================

@app.post("/chat/{agent_role}", response_model=ChatResponse)
async def chat_endpoint(agent_role: str, request: ChatRequest):
    """
    Generic chat endpoint for all agents.
    
    Roles: 'gm', 'researcher', 'coach', 'writer'
    """
    if not FACTORY:
        raise HTTPException(status_code=503, detail="Server initializing")
        
    # Determine Scopes based on Role and Request
    # Map Aliases to Base Roles for scoping defaults
    base_role_map = {
        "narrator": "gm", "rulekeeper": "gm",
        "screenwriter": "writer",
        "psychologist": "coach",
        "coder": "researcher"
    }
    base_role = base_role_map.get(agent_role, agent_role)
    
    scopes = []
    
    if base_role == "gm":
        # Global system + Campaign specific (using session_id or user_id as proxy)
        scopes = ["global:trpg", "global:blades_in_the_dark"]
        if request.user_id:
            scopes.append(f"user:{request.user_id}")
            
    elif base_role == "writer":
        scopes = ["global:writing"]
        if request.project_id:
            scopes.append(f"project:{request.project_id}")
            
    elif base_role == "coach":
        scopes = ["global:psychology"]
        if request.user_id:
            scopes.append(f"user:{request.user_id}")
            
    elif base_role == "researcher":
        scopes = ["global:research"]
            
    # Build Agent at Runtime with RAG Context
    try:
        agent = FACTORY.create_agent(
            role=agent_role, # Pass specific alias to factory
            scopes=scopes,
            query=request.query
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    
    # Construct initial state
    initial_state = {
        "messages": [HumanMessage(content=request.query)],
        "user_id": request.user_id,
        "agent_role": agent_role, # Inject specific persona
        "active_scopes": scopes,
        **request.extra_context
    }
    
    # Agent-specific state mapping (using base_role)
    if base_role == "writer":
        if not request.project_id:
            request.project_id = f"proj_{request.user_id}"
        initial_state["project_id"] = request.project_id
        initial_state["current_outline"] = request.query
    elif base_role == "coach":
        if request.role_mode:
            initial_state["user_mood_analysis"] = request.role_mode
    elif base_role == "researcher":
        # Ensure search_queries is init
        pass

    # Run Agent
    try:
        config = {"configurable": {"thread_id": request.session_id}}
        final_state = await agent.ainvoke(initial_state, config=config)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    
    # Extract response
    messages = final_state.get("messages", [])
    last_response = ""
    if messages and isinstance(messages[-1], BaseMessage):
        last_response = messages[-1].content
    elif messages and isinstance(messages[-1], dict):
        last_response = messages[-1].get("content", "")
    
    if agent_role == "writer" and final_state.get("draft_content"):
        if not last_response:
            last_response = final_state["draft_content"]
            
    clean_state = {k: v for k, v in final_state.items() if k not in ["messages", "retrieved_docs"]}
    
    return ChatResponse(
        response=str(last_response),
        final_state=clean_state
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
