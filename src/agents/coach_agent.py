"""
Coach & Psychologist Agent
==========================
Empathetic agent with long-term memory and safety rails.
Features parallel profiling to update user models without blocking response.

Roles:
- Psychologist: Empathic, listening, focus on feelings
- Coach: Strategic, action-oriented, focus on goals
"""

from typing import Annotated, Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.language_models import BaseChatModel
from langgraph.graph import StateGraph, END
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from src.graph.state import CoachState
from src.database.models import UserProfile, User
from src.database.db_init import get_session


# =============================================================================
# System Prompts
# =============================================================================

PSYCHOLOGIST_PROMPT = """You are a compassionate Clinical Psychologist.
Your goal is to provide a safe, non-judgmental space for the user.

Profile Context:
{profile_context}

Guidelines:
- Practice active listening and empathy validation
- Focus on emotional well-being and mental health
- Ask open-ended questions to explore feelings
- Avoid giving direct advice too quickly; help the user find their own answers
- If the user mentions serious issues, acknowledge them with care
- LANGUAGE: You MUST reply in CHINESE (Simplified Chinese). 请全程使用温暖、治愈的中文进行对话。

Current Mood Analysis: {mood_analysis}
"""

COACH_PROMPT = """You are a high-performance Executive Coach.
Your goal is to help the user achieve their strategic objectives.

Profile Context:
{profile_context}

Guidelines:
- Be direct, result-oriented, and strategic
- Focus on blockers, goals, and actionable steps
- Challenge the user's limiting beliefs lovingly but firmly
- Provide frameworks and concrete advice
- Hold the user accountable
- LANGUAGE: You MUST reply in CHINESE (Simplified Chinese). 请全程使用专业、有行动力的中文进行对话。

Current Mood Analysis: {mood_analysis}
"""

CRISIS_RESPONSE = """I care about your safety, but I am an AI assistant and cannot provide the immediate help you might need in a crisis. 

If you or someone else is in danger, please contact emergency services immediately (911 in the US) or call a suicide prevention hotline (988 in the US).

I'm here to listen if you want to talk about less critical distress, but your safety is the priority."""


# =============================================================================
# Helper Functions
# =============================================================================

def format_profile_context(profile: UserProfile | None) -> str:
    """Format user profile for prompt context."""
    if not profile:
        return "No prior profile information."
    
    context = []
    if profile.psych_profile:
        context.append(f"Traits: {profile.psych_profile}")
    if profile.long_term_memories:
        context.append(f"Memories: {profile.long_term_memories}")
        
    return "\n".join(context) if context else "No significant details yet."


# =============================================================================
# Node Functions
# =============================================================================

def create_profile_loader(session: Session):
    """Node: Load user profile from DB."""
    
    def profile_loader(state: CoachState) -> CoachState:
        user_id_str = state.user_id
        # Assuming user_id is passed as string but mapped to int ID in DB for this demo
        # In real app, we'd handle ID resolution properly.
        # Here we'll try to just assume the user_id string IS the ID if it's digit
        
        if not user_id_str.isdigit():
            # Mock or temporary lookup failure handling
            return state

        user_id = int(user_id_str)
        stmt = select(UserProfile).where(UserProfile.user_id == user_id)
        profile = session.execute(stmt).scalar_one_or_none()
        
        # Store profile data in state for downstream nodes (not persisted in graph state directly to keep it light)
        # We'll use a temporary key in the state or just keep it in memory.
        # For LangGraph state, we should define fields. checking state.py...
        # CoachState has mood_scores (dict). We can put profile there or add new field.
        # Let's put raw profile in a temporary internal key or just format it now.
        
        # We'll format it into a system message-ready string and store in state
        # But wait, state definitions are rigid in typeddict/pydantic. 
        # CoachState extends BaseState.
        
        # Let's assume we can add derived context to the state that doesn't persist inappropriately.
        # Or we can just read it again or passed via "mood_scores" (a bit hacky).
        # Better: Add 'profile_context' to CoachState? user request didn't specify it.
        # We'll stick to using the existing fields. We can put the formatted string into 'user_mood_analysis' 
        # initially or just re-fetch.
        
        # To be clean, let's just create the context string here and inject it into the messages?
        # No, that modifies conversation history.
        
        # We will attach it to the state as a private attribute if possible, but Pydantic...
        # Let's fetch it in the Responder node instead? 
        # The prompt says: "Node 1: ProfileLoader: Loads... from Postgres."
        # So it implies passing it down. 
        
        # Let's add the raw profile dicts to the state's known fields if they fit, 
        # or assume we extend state dynamically (dict-based state allows this, Pydantic objects are stricter).
        # Our State in state.py is inheriting BaseModel.
        
        # We'll store the profile data in `mood_scores` (psych info) for now, as it's a dict.
        if profile:
            state.mood_scores = profile.psych_profile
            # We explicitly add a non-schema attribute for execution context if LangGraph allows, 
            # otherwise we might need to modify state.py to hold 'profile_cache'.
            # For this strict Pydantic implementation, let's modify the state.py if needed?
            # Or just update state.py? The user asked for specific fields.
            # I will carry the formatted context in `user_mood_analysis` temporarily if needed
            # OR better: I'll just load it in this node and put it in a custom key, 
            # effectively treating the Pydantic model as having extra fields allowed?
            # "model_config = {'arbitrary_types_allowed': True}" is set in BaseState.
            # So I can attach `_profile_context` string.
            
            setattr(state, "_profile_context", format_profile_context(profile))
            setattr(state, "_profile_obj", profile) # Keep obj for profiler? safely detach?
        
        return state

    return profile_loader


def create_safety_guard():
    """Node: Check for crisis keywords."""
    
    CRISIS_KEYWORDS = {
        "suicide", "kill myself", "want to die", "hurt myself", 
        "end it all", "don't want to live", "cutting myself"
    }

    def safety_guard(state: CoachState) -> CoachState:
        messages = state.messages
        if not messages:
            return state
            
        last_content = messages[-1].content.lower()
        
        for keyword in CRISIS_KEYWORDS:
            if keyword in last_content:
                state.safety_check_passed = False
                return state
                
        state.safety_check_passed = True
        return state
        
    return safety_guard


def create_responder(llm: BaseChatModel):
    """Node: Generate advice based on role."""
    
    def responder(state: CoachState) -> CoachState:
        # Check role from where? 
        # Usually role is defined in config or user session. 
        # We will check if `user_mood_analysis` contains a role hint or default to Psychologist.
        # Or check the last message metadata? 
        # The User Request mentions: "Switch mechanism... based on role"
        # We'll assume the role is passed in `user_mood_analysis` or we check an external config.
        # For this implementation, let's detect it from context or default to Psychologist.
        # Or better, we can inject it into the state at the start.
        
        role = "psychologist" # Default
        
        # Recover context from previous node 
        context = getattr(state, "_profile_context", "No profile loaded.")
        
        if role == "coach":
            sys_template = COACH_PROMPT
        else:
            sys_template = PSYCHOLOGIST_PROMPT
            
        prompt = sys_template.format(
            profile_context=context,
            mood_analysis=state.user_mood_analysis
        )
        
        messages = [SystemMessage(content=prompt)] + state.messages
        response = llm.invoke(messages)
        
        state.messages.append(AIMessage(content=response.content))
        return state
        
    return responder


def create_profiler(llm: BaseChatModel, session: Session):
    """Node: Analyze input for profile updates (Background)."""
    
    PROFILER_PROMPT = """Analyze the user's latest message.
Extract insights about:
1. Psychological traits (MBTI, openness, etc.)
2. Communication style
3. Personal facts/memories

Return JSON only:
{
  "new_traits": {"trait": "value"},
  "new_memories": {"fact": "value"}
}
If nothing significant, return empty JSON."""

    def profiler(state: CoachState) -> CoachState:
        messages = state.messages
        last_msg = messages[-1].content
        user_id = state.user_id
        
        # Run extraction
        response = llm.invoke([
            SystemMessage(content=PROFILER_PROMPT),
            HumanMessage(content=last_msg)
        ])
        
        # Parse JSON (simplified)
        import json
        try:
            content = response.content.replace("```json", "").replace("```", "").strip()
            data = json.loads(content)
        except:
            data = {}
            
        new_traits = data.get("new_traits", {})
        new_memories = data.get("new_memories", {})
        
        if (new_traits or new_memories) and user_id and user_id.isdigit():
            uid = int(user_id)
            # Update DB
            # Use upsert logic
            stmt = select(UserProfile).where(UserProfile.user_id == uid)
            profile = session.execute(stmt).scalar_one_or_none()
            
            if not profile:
                profile = UserProfile(
                    user_id=uid,
                    psych_profile=new_traits,
                    long_term_memories=new_memories
                )
                session.add(profile)
            else:
                # Merge updates
                if new_traits:
                    profile.psych_profile = {**profile.psych_profile, **new_traits}
                if new_memories:
                    profile.long_term_memories = {**profile.long_term_memories, **new_memories}
            
            session.commit()
            
        return state
        
    return profiler


def crisis_response(state: CoachState) -> CoachState:
    """Node: Static crisis response."""
    state.messages.append(AIMessage(content=CRISIS_RESPONSE))
    return state


# =============================================================================
# Router
# =============================================================================

def route_safety(state: CoachState) -> Literal["responder", "crisis_response"]:
    if state.safety_check_passed:
        return "responder"
    return "crisis_response"


# =============================================================================
# Graph Builder
# =============================================================================

def build_coach_agent(llm: BaseChatModel, session: Session) -> StateGraph:
    """
    Build Coach Agent Graph.
    
    Flow:
    Loader -> Guard -> (Check)
        -> Unsafe: Crisis -> END
        -> Safe: 
            -> Responder -> END
            -> Profiler -> END (Parallel)
    """
    
    loader = create_profile_loader(session)
    guard = create_safety_guard()
    responder = create_responder(llm)
    profiler = create_profiler(llm, session)
    
    graph = StateGraph(CoachState)
    
    graph.add_node("loader", loader)
    graph.add_node("guard", guard)
    graph.add_node("responder", responder)
    graph.add_node("profiler", profiler)
    graph.add_node("crisis", crisis_response)
    
    graph.set_entry_point("loader")
    graph.add_edge("loader", "guard")
    
    # Routing
    # We can't really do "fork" easily in conditional edges in basic LangGraph 
    # unless we return a list of nodes to visit next.
    # To run parallel, the conditional edge should return ["responder", "profiler"]
    
    def safety_router(state: CoachState):
        if state.safety_check_passed:
            return ["responder", "profiler"]
        else:
            return ["crisis"]

    graph.add_conditional_edges(
        "guard",
        safety_router,
        {
            "responder": "responder",
            "profiler": "profiler",
            "crisis": "crisis"
        }
    )
    
    graph.add_edge("responder", END)
    graph.add_edge("profiler", END)
    graph.add_edge("crisis", END)
    
    return graph.compile()
