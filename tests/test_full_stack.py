"""
Full Stack Integration Test (FAT)
=================================
Verifies the existence and basic functionality of all 9 required personas.
Mocks DB and LLM to focus on Architecture wiring.
"""

import pytest
from unittest.mock import MagicMock, ANY
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.language_models import FakeListChatModel

from backend.utils.agent_factory import AgentFactory
from backend.database.models import UserProfile, GameState
from backend.graph.state import BaseState

# The 9 Required Personas
PERSONAS = [
    # TRPG
    ("gm", "TRPG Game Master"), 
    ("narrator", "TRPG Narrator"),      # Currently Alias -> GM
    ("rulekeeper", "TRPG Rulekeeper"),  # Currently Alias -> GM
    
    # Coach
    ("psychologist", "Psychologist"),   # Currently Alias -> Coach
    ("coach", "Life/Career Coach"),     # Generic Coach
    
    # Writer
    ("writer", "Novelist"),
    ("screenwriter", "Screenwriter"),   # Currently Alias -> Writer
    
    # Researcher
    ("researcher", "Deep Researcher"),
    ("coder", "Code Coach")             # Currently Alias -> Researcher
]

@pytest.fixture
def mock_session():
    """Mock SQLAlchemy Session"""
    session = MagicMock()
    # Mock specific return values if nodes query DB
    session.execute.return_value.scalars.return_value.all.return_value = []
    session.execute.return_value.scalar_one_or_none.return_value = None
    return session

@pytest.fixture
def mock_llm():
    """Fake LLM that just echoes"""
    return FakeListChatModel(responses=["[MOCK] Agent Response"] * 100)

@pytest.fixture
def factory(mock_llm, mock_session):
    return AgentFactory(llm=mock_llm, session=mock_session)

@pytest.mark.asyncio
@pytest.mark.parametrize("role, name", PERSONAS)
async def test_persona_wiring(factory, role, name):
    """
    Test that every persona:
    1. Can be instantiated (AgentFactory)
    2. Can accept a user message
    3. Returns a valid state update
    """
    print(f"\nTesting wiring for: {name} ({role})...")
    
    # factory.create_agent currently enforces strict roles. 
    # This test expects failure for unimplemented aliases if factory is strict.
    
    try:
        # 1. Instantiate
        # Note: Factory needs 'scopes' and 'query'
        agent = factory.create_agent(role=role, scopes=["global:test"], query="Hello")
        
        # 2. Invoke (Mock State)
        # We need to construct the correct initial state. 
        # Since we don't know the exact class (GMState vs WriterState) easily here without logic,
        # we pass a dict which LangGraph accepts.
        
        initial_state = {
            "messages": [HumanMessage(content="Hello AI")],
            "user_id": "test_user",
            "session_id": "test_session",
            "active_scopes": ["global:test"],
            "strict_mode": False,
            "agent_role": role  # New field required
        }
        
        # Inject required fields for specific agents to avoid validation error
        if role in ["gm", "narrator", "rulekeeper"]:
             initial_state["game_state"] = {}
             initial_state["inventory"] = []
             
        if role in ["writer", "screenwriter"]:
             initial_state["current_outline"] = "Test Outline"
             initial_state["project_id"] = "test_project"
             
        if role in ["researcher", "coder"]:
             initial_state["search_queries"] = []
             
        if role in ["coach", "psychologist"]:
             initial_state["user_mood_analysis"] = "Neutral" # MUST be string, not dict
        
        # Run
        response = await agent.ainvoke(initial_state)
        
        # 3. Verify
        assert "messages" in response
        last_msg = response["messages"][-1]
        assert isinstance(last_msg, AIMessage)
        # Check if we got the mock response (or handled internally)
        # Note: FakeListChatModel responses might be consumed by internal chains
        print(f"✅ {name} Wiring PASS")
        
    except ValueError as e:
        # Factory raises ValueError for unknown roles
        pytest.fail(f"❌ {name} instantiation FAILED: {str(e)}")
    except Exception as e:
        pytest.fail(f"❌ {name} runtime FAILED: {str(e)}")
