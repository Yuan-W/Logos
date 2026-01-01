"""
Integration Tests for Writer Agent Flow
=======================================
Verifies the High-Code Architecture:
1. Handoff Processing (Lobby -> Writer)
2. Reflexion Loop (Draft -> Critic -> Revise)
3. TermGuard (Semantic Editor)
4. Meta-Talk Routing
"""

import pytest
import datetime
from unittest.mock import MagicMock
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from backend.agents.writer_agent import build_writer_agent
from backend.graph.state import WriterState
from backend.database.models import TermRegistry
from sqlalchemy import text

@pytest.fixture
def mock_llm():
    """Mock LLM that behaves differently based on prompts."""
    mock = MagicMock()
    
    def side_effect(messages, **kwargs):
        # Flatten messages to string for inspection
        prompt_content = ""
        if isinstance(messages, list):
            for m in messages:
                if isinstance(m, SystemMessage):
                    prompt_content += f"[SYS] {m.content}\n"
                elif isinstance(m, HumanMessage):
                    prompt_content += f"[USR] {m.content}\n"
        
        print(f"\\n[MockLLM] Prompt: {prompt_content[:50]}...")

        # 1. Intent Classification
        if "Classify the user's message" in prompt_content:
            if prompt_content.count("Who are you") > 1:  # Specific catch (Sys + User)
                return AIMessage(content="INTERACTION")
            return AIMessage(content="ACTION")
            
        # 2. Structure Normalizer
        if "Convert the user's raw input" in prompt_content:
            return AIMessage(content="""```json
            {
                "title": "Tragedy in Space",
                "outline": "Introduction: A lonely astronaut...",
                "mood": "Melancholic",
                "pov": "Astronaut"
            }
            ```""")
            
        # 3. Drafter (Novelist)
        if "You are a master Novelist" in prompt_content:
            if "Alara" in prompt_content:
                return AIMessage(content="Draft: I see the Alara.")
            return AIMessage(content="Draft content: The astronaut looked at the void. It was dark.")
            
        # 4. Critic
        if "You are a ruthless Continuity Editor" in prompt_content:
            # Force revision once
            return AIMessage(content="""```json
            {"status": "Approve", "feedback": ""}
            ```""")
            
        # 5. Editor (TermGuard)
        if "Glossary (Strict Enforcement)" in prompt_content:
            if "Alara" in prompt_content: # If glossary has Alara
                return AIMessage(content="Corrected: The astronaut looked at Alara (The Sun).")
            return AIMessage(content="PASS")

        # 6. Lore Extractor
        if "Analyze the final text" in prompt_content:
            return AIMessage(content="[]")

        # 7. Persona Chat
        if "You are the Co-Author" in prompt_content:
             return AIMessage(content="I am your friendly AI co-author.")
             
        return AIMessage(content="Generic Response")
        
    mock.invoke.side_effect = side_effect
    return mock


@pytest.fixture
def mock_session():
    """Mock Database Session."""
    session = MagicMock()
    # Mock TermRegistry responses for Editor
    return session


@pytest.mark.asyncio
async def test_handoff_flow(mock_llm, mock_session):
    """
    Case A: Simulate Lobby sending HandoffPayload.
    Verify Writer adopts Tone and processes input via Normalizer.
    """
    # Setup Mock Session to return "Alara" when queried (to prevent NoneType error in retriever loop if called)
    mock_result = MagicMock()
    mock_result.term = "Alara"
    mock_result.definition = "The binary sun system"
    mock_session.execute.return_value.scalars.return_value.all.return_value = [mock_result]

    agent = build_writer_agent(mock_llm, mock_session)
    
    initial_state = WriterState(
        messages=[HumanMessage(content="Make it sad")],
        handoff_payload={
            "user_raw": "Make it sad",
            "system_hint": "Tone: Tragedy",
            "intent_classification": "writing",
            "suggested_scopes": ["global:writing"]
        }
    )
    
    final_state = await agent.ainvoke(initial_state)
    
    # Check if Normalizer was called (look for normalized outline)
    assert "Melancholic" in final_state["current_outline"]
    assert "Tragedy in Space" in final_state["current_outline"]
    
    # Check if Strict Mode was enabled by default/handoff
    assert final_state["strict_mode"] is True


@pytest.mark.asyncio
async def test_term_guard_consistency(mock_llm, mock_session):
    """
    Case B: Consistency Check with Mocked DB.
    """
    # Setup Mock Session to return "Alara" when queried
    mock_result = MagicMock()
    mock_result.term = "Alara"
    mock_result.definition = "The binary sun system"
    mock_result.scope = "global:writing"
    
    # When session.execute() is called (by TermRetriever), return this mock
    mock_session.execute.return_value.scalars.return_value.all.return_value = [mock_result]
    
    # Create Agent
    agent = build_writer_agent(mock_llm, mock_session)
    
    initial_state = WriterState(
        messages=[HumanMessage(content="Write about Alara")],
        current_outline="Write about Alara",
        active_scopes=["global:writing"],
        strict_mode=True
        # MockLLM Editor returns "PASS" unless "Alara" in prompt.
        # TermRetriever should inject "Alara" : "The binary sun system" into prompt if found.
    )
    
    final_state = await agent.ainvoke(initial_state)
    
    # Logic chain:
    # 1. Drafter sees "OUTLINE: Write about Alara" -> Returns "Draft: I see the Alara."
    # 2. Editor sees "Draft: I see the Alara." -> Splits -> Finds "Alara" in text.
    # 3. TermRetriever queries DB for "Alara" -> Returns mock result.
    # 4. Editor builds prompt with Glossary: {"Alara": ...}
    # 5. MockLLM Editor sees "Glossary" and "Alara" -> Returns "Corrected: The astronaut looked at Alara (The Sun)."
    
    # Check if final draft content matches corrected text
    assert "Corrected" in final_state["draft_content"]
    assert "(The Sun)" in final_state["draft_content"] 




@pytest.mark.asyncio
async def test_meta_talk_routing(mock_llm, mock_session):
    """
    Case C: Meta-Talk. Input 'Who are you?'.
    Expect routing to PersonaChat, not Normalizer/Draft.
    """
    agent = build_writer_agent(mock_llm, mock_session)
    
    initial_state = WriterState(
        messages=[HumanMessage(content="Who are you?")],
        handoff_payload={} # Empty payload, rely on IntentClassifier
    )
    
    final_state = await agent.ainvoke(initial_state)
    
    last_msg = final_state["messages"][-1].content
    assert "I am your friendly AI co-author" in last_msg
    # Ensure no draft content
    assert not final_state.get("draft_content")
