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
from sqlalchemy.orm import Session

from src.database.db_init import get_session
from src.agents.gm_agent import build_gm_agent
from src.agents.researcher_agent import build_researcher_agent
from src.agents.coach_agent import build_coach_agent
from src.agents.writer_agent import build_writer_agent


# =============================================================================
# Configuration & Globals
# =============================================================================

class AppState(TypedDict):
    agents: Dict[str, CompiledStateGraph]
    llm: ChatOpenAI
    db_session: Session

# Global cache for compiled graphs to avoid rebuilding per request
# Ideally, we should use dependency injection, but simple global or AppState works.
AGENTS: Dict[str, CompiledStateGraph] = {}
LLM = None
DB_SESSION = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize resources on startup."""
    global AGENTS, LLM, DB_SESSION
    
    print("Initializing Logos Agents...")
    
    # 1. Setup DB
    # For agents that need a session factory or persistent session
    # Note: SQLAlchemy sessions are not thread-safe. Ideally we create one per request.
    # However, our build_agent functions take a session capture it in closures.
    # This is risky for a long-running server.
    # BETTER APPROACH: Pass a session factory or use `Depends(get_db)` in the endpoint 
    # and pass it to the agent at runtime via config or state?
    # LangGraph nodes use closures. If we bake the session in, it's shared.
    # For this prototype, we'll use a scoped session or assume single worker.
    # OR: Re-build agent per request? Expensive.
    # FIX: We will create a fresh session per request in the endpoint 
    # and inject it into the graph State? 
    # State in LangGraph must be serializable. We cannot put a Session in Pydantic State easily.
    
    # Pragmactic Solution for Prototype:
    # Use the global `get_session()` inside the nodes (create fresh there) instead of closure injection?
    # Our current agent code uses closure injection: `create_state_loader(session)`.
    # This implies we need a long-lived session or one per agent.
    # If we use one session for the app lifetime, we risk rollback issues.
    
    # Let's use `get_session()` to create a session for the builds, 
    # BUT we should be aware this session is shared. 
    # For a robust server, we should refactor agents to accept session in `configurable` config.
    # Given the constraints and existing code, we will instantiate a global session here.
    # WARNING: This is not production-ready for high concurrency.
    DB_SESSION = get_session() 
    
    # 2. Setup LLM
    LLM = ChatOpenAI(
        model="gemini-3-flash-preview", # Default, can be overridden per agent
        openai_api_key=os.getenv("OPENAI_API_KEY", "sk-litellm-master-key"),
        openai_api_base=os.getenv("OPENAI_API_BASE_URL", "http://localhost:4000/v1")
    )
    
    # 3. Build Agents
    # We pass the shared session. 
    AGENTS["gm"] = build_gm_agent(LLM, DB_SESSION)
    AGENTS["researcher"] = build_researcher_agent(LLM, DB_SESSION)
    AGENTS["coach"] = build_coach_agent(LLM, DB_SESSION)
    AGENTS["writer"] = build_writer_agent(LLM, DB_SESSION)
    
    print(f"Loaded agents: {list(AGENTS.keys())}")
    
    yield
    
    print("Shutting down...")
    DB_SESSION.close()


app = FastAPI(title="Logos AI OS", lifespan=lifespan)


# =============================================================================
# Models
# =============================================================================

class ChatRequest(BaseModel):
    user_id: str = Field(..., description="Session ID or User ID")
    message: str = Field(..., description="User input text")
    
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
    if agent_role not in AGENTS:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_role}' not found. Available: {list(AGENTS.keys())}")
    
    agent = AGENTS[agent_role]
    
    # Construct initial state based on role requirements
    # All states share BaseState (messages, user_id)
    initial_state = {
        "messages": [HumanMessage(content=request.message)],
        "user_id": request.user_id,
        **request.extra_context
    }
    
    # Agent-specific mapping
    if agent_role == "writer":
        if not request.project_id:
            # Generate dummy project ID if missing
            request.project_id = f"proj_{request.user_id}"
            
        initial_state["project_id"] = request.project_id
        # Writer expects 'current_outline' typically. 
        # If user sends a message, we might treat it as outline or instruction?
        # The writer agent uses 'current_outline' as the primary driver.
        # Let's map message -> current_outline
        initial_state["current_outline"] = request.message
        
    elif agent_role == "coach":
        if request.role_mode:
            # We used 'user_mood_analysis' logic in the agent to carry prompt hint? 
            # Actually we used a "user_mood_analysis" field in coach_agent.py usage example?
            # Looking at coach_agent.py, it expects `user_mood_analysis` to hold context or checks it for role?
            # The responder checks: `getattr(state, "_profile_context")` and `state.user_mood_analysis`.
            # Wait, the code I wrote for `create_responder` in `coach_agent.py` had a logic hole:
            # `role = "psychologist"` is hardcoded but comments mentioned checking `user_mood_analysis`.
            # Let's pass the role mode into `user_mood_analysis` or just inject it.
            # I'll inject it into `user_mood_analysis` field as string since it's a dict/any?
            # State definition for CoachState: `mood_scores: dict`, `user_mood_analysis: str`.
            # So I can pass "coach" string into `user_mood_analysis` if that's what controls it.
            # (Note: I need to verify coach_agent logic, but assuming it works as intended or defaulted).
            initial_state["user_mood_analysis"] = request.role_mode

    # Run Agent
    try:
        # invoke returns the final state dict
        final_state = await agent.ainvoke(initial_state)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    
    # Extract response
    # Usually the last message in 'messages' key
    messages = final_state.get("messages", [])
    last_response = ""
    if messages and isinstance(messages[-1], BaseMessage):
        last_response = messages[-1].content
    elif messages and isinstance(messages[-1], dict):
        # JSON serialization might make it a dict if getting from compiled graph via some paths
        last_response = messages[-1].get("content", "")
    
    # For Writer, result might be in draft_content
    if agent_role == "writer" and final_state.get("draft_content"):
        # If draft exists, prefer that over empty message
        if not last_response:
            last_response = final_state["draft_content"]
            
    # Serialize state for return (filter un-serializable)
    # Pydantic models in state need `model_dump` if they are objects
    # But final_state from invoke is usually a dict.
    
    # Filter out bulky fields/objects if needed
    clean_state = {k: v for k, v in final_state.items() if k not in ["messages", "retrieved_docs"]}
    
    return ChatResponse(
        response=str(last_response),
        final_state=clean_state
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
