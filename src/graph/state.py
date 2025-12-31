"""
Grand Unified State Definitions
===============================
Pydantic-based LangGraph state definitions with polymorphic inheritance.
"""

from typing import Annotated, Any

from langchain_core.documents import Document
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


# =============================================================================
# Base State
# =============================================================================

class BaseState(BaseModel):
    """
    Base state for all agents.
    Uses Annotated with add_messages for proper message accumulation in LangGraph.
    """
    messages: Annotated[list[BaseMessage], add_messages] = Field(default_factory=list)
    user_id: str = Field(default="", description="Current user identifier")
    
    model_config = {"arbitrary_types_allowed": True}


# =============================================================================
# Game State (TRPG: DM, Rulekeeper, Narrator)
# =============================================================================

class GameState(BaseState):
    """
    State for TRPG gameplay agents.
    Tracks dice rolls, rule checks, and player HP.
    """
    dice_roll_result: int = Field(default=0, description="Last dice roll result")
    rule_check_result: str = Field(default="", description="Result of rule validation")
    current_hp: dict[str, int] = Field(
        default_factory=dict, 
        description="Current HP for all characters: {'player': 25, 'goblin': 10}"
    )
    
    # Extended game context
    current_scene: str = Field(default="", description="Current scene description")
    active_npcs: list[str] = Field(default_factory=list, description="NPCs in current scene")
    pending_actions: list[str] = Field(default_factory=list, description="Actions awaiting resolution")


# =============================================================================
# Research State (Researcher, Coder)
# =============================================================================

class ResearchState(BaseState):
    """
    State for research and coding agents.
    Manages search queries, retrieved documents, and draft answers.
    """
    search_queries: list[str] = Field(
        default_factory=list, 
        description="Generated search queries"
    )
    retrieved_docs: list[Document] = Field(
        default_factory=list, 
        description="Retrieved documents from vector store"
    )
    draft_answer: str = Field(default="", description="Current draft response")
    
    # Extended research context
    sources_cited: list[str] = Field(default_factory=list, description="URLs/references cited")
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Answer confidence")


# =============================================================================
# Coach State (Life Coach, Psychologist)
# =============================================================================

class CoachState(BaseState):
    """
    State for coaching and psychological support agents.
    Includes mood analysis and safety checks.
    """
    user_mood_analysis: str = Field(
        default="", 
        description="Analysis of user's current emotional state"
    )
    safety_check_passed: bool = Field(
        default=True, 
        description="False if crisis intervention needed"
    )
    
    # Extended coaching context
    mood_scores: dict[str, float] = Field(
        default_factory=dict,
        description="Mood dimensions: {'stress': 0.7, 'motivation': 0.4, 'anxiety': 0.3}"
    )
    suggested_actions: list[str] = Field(
        default_factory=list, 
        description="Recommended actions for user"
    )
    session_goals: list[str] = Field(
        default_factory=list,
        description="Goals for current session"
    )


# =============================================================================
# Writer State (Novelist)
# =============================================================================

class WriterState(BaseState):
    """
    State for creative writing agents.
    Manages plot outline, chapters, and editorial feedback.
    """
    # Inputs
    current_outline: str = Field(default="", description="Summary of chapter/scene to write")
    project_id: str = Field(default="", description="Current project identifier")
    
    # Internal working state
    retrieved_lore: str = Field(default="", description="Context from StoryBible")
    draft_content: str = Field(default="", description="Generated raw text")
    critique_notes: str = Field(default="", description="Feedback from Critic")
    iteration_count: int = Field(default=0, description="Reflexion loop counter")
    
    # Legacy/Extended fields
    plot_outline: list[str] = Field(default_factory=list, description="Full book outline")
    character_stats: dict[str, Any] = Field(default_factory=dict)
    word_count: int = Field(default=0)


# =============================================================================
# Type Aliases for LangGraph
# =============================================================================

# These can be used in graph definitions:
# graph = StateGraph(GameState)
# graph = StateGraph(ResearchState)
# etc.
