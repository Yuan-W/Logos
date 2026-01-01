"""
Logos API Gateway
=================
FastAPI server exposing multi-agent workflows.

Endpoints:
- POST /chat/{agent_role}: Legacy request/response endpoint.
- GET /stream/{session_id}: SSE endpoint for event streaming (Headless API).
- GET /sessions: List active sessions.
- GET /profile: Get user profile.

Supported Roles:
- gm (Dungeon Master)
- researcher (Deep Researcher)
- coach (Psychologist/Coach)
- writer (Novelist/Screenwriter)
"""

import json
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any, List, Optional
from typing_extensions import TypedDict

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, BaseMessage
from langchain_openai import ChatOpenAI

from sqlalchemy import select, distinct
from sqlalchemy.orm import Session as DBSession

from backend.database.models import User, UserProfile, ConversationLog, GameState as GameStateDB
from backend.gateway.lifecycle import init_globals, shutdown_globals, get_agent_factory

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api")

# --- Lifecycle ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize resources on startup via lifecycle module."""
    await init_globals()
    yield
    await shutdown_globals()


app = FastAPI(title="Logos AI OS", lifespan=lifespan)

# --- Middleware ---

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite default
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Dependencies ---

def get_db():
    # Helper to get session from factory's global session or create new?
    # Factory uses a global session. For API endpoints that need DB, we should probably
    # use the same session or create a new one. 
    # Since lifecycle creates a global DB_SESSION, we can access it via factory or direct.
    # But usually for FastAPI we want dependencies. 
    # Let's import get_session from db_init for independent reads.
    from backend.database.db_init import get_session
    db = get_session()
    try:
        yield db
    finally:
        db.close()


# --- Models ---

class ChatRequest(BaseModel):
    user_id: str = Field(..., description="User identifier")
    query: str = Field(..., description="User input text")
    session_id: str = Field(..., description="Session/Thread ID for state isolation")
    extra_context: Optional[Dict[str, Any]] = Field(default_factory=dict)

class ChatResponse(BaseModel):
    response: str
    final_state: Dict[str, Any]

class SessionInfo(BaseModel):
    session_id: str
    last_message: Optional[str] = None
    updated_at: Optional[str] = None

class UserProfileDTO(BaseModel):
    username: str
    email: str
    preferences: Dict[str, Any]


# --- Endpoints ---

@app.get("/health")
async def health_check():
    """Health check endpoint for Docker/Kubernetes."""
    return {"status": "healthy"}


@app.get("/sessions", response_model=List[SessionInfo])
async def list_sessions(db: DBSession = Depends(get_db)):
    """List chat history/active sessions."""
    stmts = select(GameStateDB).order_by(GameStateDB.updated_at.desc())
    results = db.execute(stmts).scalars().all()
    
    sessions = []
    for gs in results:
        sessions.append(SessionInfo(
            session_id=gs.session_id,
            updated_at=gs.updated_at.isoformat() if gs.updated_at else None,
            last_message="" 
        ))
    return sessions


@app.get("/profile", response_model=UserProfileDTO)
async def get_profile(db: DBSession = Depends(get_db)):
    """Get current user settings."""
    stmt = select(User).limit(1)
    user = db.execute(stmt).scalar_one_or_none()
    
    if not user:
        return UserProfileDTO(
            username="Guest",
            email="guest@example.com",
            preferences={}
        )
    
    profile_data = {}
    if user.profile:
        profile_data = user.profile.psych_profile or {}
        
    return UserProfileDTO(
        username=user.username,
        email=user.email,
        preferences=profile_data
    )


@app.get("/stream/{session_id}")
async def stream_workflow(
    session_id: str, 
    request: Request,
):
    """
    SSE Endpoint for LangGraph events.
    Query Params:
    - message: The user input message.
    - role: The agent role (default: gm).
    - user_id: User identifier (default: user_default).
    """
    params = request.query_params
    user_message = params.get("message")
    role = params.get("role", "gm")
    user_id = params.get("user_id", "user_default")

    if not user_message:
        async def waiting_gen():
            yield "event: system\ndata: {\"status\": \"connected\", \"info\": \"Waiting for input\"}\n\n"
        return StreamingResponse(waiting_gen(), media_type="text/event-stream")

    # 1. Get Factory & Agent
    try:
        factory = get_agent_factory()
    except RuntimeError:
        # Fallback handling if headers/startup not ready?
        # Should be covered by startup
        raise HTTPException(status_code=503, detail="Server initializing")

    # Determine scopes (simplified logic from chat_endpoint)
    # TODO: Unify scope logic into a helper
    scopes = []
    if role in ["gm", "narrator"]:
        scopes = ["global:trpg", "global:blades_in_the_dark", f"user:{user_id}"]
    elif role == "writer":
        scopes = ["global:writing", f"project:proj_{user_id}"]
    
    # Create Graph
    try:
        graph = factory.create_agent(role=role, scopes=scopes, query=user_message)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 2. Define Generator
    async def event_generator():
        # Input State
        input_state = {
            "messages": [HumanMessage(content=user_message)],
            "user_id": session_id,  # Map session_id to user_id in state for persistence
            "agent_role": role,
            "conversation_summary": "" 
        }
        
        # Config for persistence
        config = {"configurable": {"thread_id": session_id}}

        # Stream
        async for event in graph.astream_events(input_state, config=config, version="v2"):
            kind = event["event"]
            
            # 1. Text Tokens
            if kind == "on_chat_model_stream":
                # Filter specifically for output nodes (narrator, storyteller, or final responder)
                # Note: 'writer' agent might use different node names.
                # 'gm' agent uses 'storyteller' and 'narrator'.
                # To be generic, we might want to ALLOW all, or filter internal agents.
                # Current 'GM' agent has 'rules_lawyer' which we want to hide.
                node_name = event.get("metadata", {}).get("langgraph_node", "")
                
                # Allow list approach - only nodes that produce user-facing content
                allowed_nodes = ["storyteller", "narrator", "agent", "responder", "writer_node", "draft", "editor"]
                
                if node_name in allowed_nodes:
                    chunk = event["data"]["chunk"]
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        payload = json.dumps({"text_chunk": chunk.content})
                        yield f"event: message\ndata: {payload}\n\n"
            
            # 2. Artifact Update (e.g. Drafts, Outlines)
            elif kind == "on_chain_end":
                data = event["data"].get("output")
                if data and isinstance(data, dict):
                    # Check for draft or outline content
                    # GM Agent uses 'draft_narrative'
                    # Writer Agent uses 'draft_content' and 'current_outline'
                    draft_content = data.get("draft_narrative") or data.get("draft_content")
                    outline_content = data.get("current_outline")
                    
                    if draft_content:
                         payload = json.dumps({
                            "type": "draft", 
                            "content": draft_content
                        })
                         yield f"event: artifact_update\ndata: {payload}\n\n"
                    
                    if outline_content:
                         payload = json.dumps({
                            "type": "outline", 
                            "content": outline_content
                        })
                         yield f"event: artifact_update\ndata: {payload}\n\n"

            # 3. Tool Calls
            elif kind == "on_tool_start":
                tool_name = event["name"]
                payload = json.dumps({"tool_name": tool_name})
                yield f"event: tool_start\ndata: {payload}\n\n"
            
            if await request.is_disconnected():
                break

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/chat/{agent_role}", response_model=ChatResponse)
async def chat_endpoint(agent_role: str, request: ChatRequest):
    """Legacy/Synchronous Chat Endpoint."""
    factory = get_agent_factory()
    
    # (Simplified scope logic for brevity - could import helper)
    scopes = ["global:trpg"] if agent_role == "gm" else []
    
    agent = factory.create_agent(role=agent_role, scopes=scopes, query=request.query)
    
    initial_state = {
        "messages": [HumanMessage(content=request.query)],
        "user_id": request.user_id,
        "agent_role": agent_role
    }
    
    config = {"configurable": {"thread_id": request.session_id}}
    final_state = await agent.ainvoke(initial_state, config=config)
    
    messages = final_state.get("messages", [])
    last_response = messages[-1].content if messages else ""
    
    clean_state = {k: v for k, v in final_state.items() if k not in ["messages"]}
    return ChatResponse(response=str(last_response), final_state=clean_state)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
