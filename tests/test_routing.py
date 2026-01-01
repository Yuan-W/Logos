"""
Layered Routing Test Suite
==========================
Tests for:
1. Lobby Agent Routing (Global Router)
2. GM Agent Intent Classification (Action vs Interaction)
3. Writer Agent Intent Classification (Work vs Chat)
"""

import pytest
from unittest.mock import MagicMock
from langchain_core.messages import HumanMessage, AIMessage

from backend.agents.lobby_agent import create_lobby_agent
from backend.agents.gm_agent import create_intent_classifier as create_gm_classifier, route_root as gm_route_root
from backend.agents.writer_agent import create_intent_classifier as create_writer_classifier, route_root as writer_route_root
from backend.graph.state import GameState, WriterState


class TestLobbyRouting:
    """Test the Lobby Agent's router."""

    def test_lobby_routes_to_gm(self):
        """Test routing 'I want to play D&D' to GM."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = AIMessage(content="gm")
        
        agent = create_lobby_agent(mock_llm)
        
        # Simulate state
        input_state = {"messages": [HumanMessage(content="I want to start a D&D game")], "next_agent": "lobby"}
        
        # Invoke 'router' node directly or the graph
        result = agent.invoke(input_state)
        
        assert result["next_agent"] == "gm"
        
    def test_lobby_routes_to_writer(self):
        """Test routing 'Help me write a novel' to Writer."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = AIMessage(content="writer")
        
        agent = create_lobby_agent(mock_llm)
        
        input_state = {"messages": [HumanMessage(content="Write a novel")], "next_agent": "lobby"}
        result = agent.invoke(input_state)
        
        assert result["next_agent"] == "writer"

    def test_lobby_stays_in_lobby(self):
        """Test general questions stay in Lobby."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = AIMessage(content="lobby")
        
        # When staying in lobby, it should call responder
        # But for this test we check the 'next_agent' output of the router logic if we could isolate it.
        # Since we use compiled graph, we can check the final state.
        # If it stays in lobby, it calls responder node which adds a message.
        
        # Need to mock the responder call too or let it run.
        # We reused the same llm for router and responder.
        # Let's simple check routing logic via the mock return.
        
        agent = create_lobby_agent(mock_llm)
        input_state = {"messages": [HumanMessage(content="Hello?")], "next_agent": "lobby"}
        
        # First call router -> lobby
        # Then calls responder -> adds message
        # So we invoke.
        
        # Mock LLM needs two responses: one for router ("lobby"), one for responder ("Hello! I am Logos.")
        mock_llm.invoke.side_effect = [
            AIMessage(content="lobby"), 
            AIMessage(content="Hello! I am Logos.")
        ]
        
        result = agent.invoke(input_state)
        
        assert result["next_agent"] == "lobby"
        assert len(result["messages"]) == 2 # 1 input + 1 output
        assert result["messages"][-1].content == "Hello! I am Logos."


class TestGMIntentRouting:
    """Test the GM Agent's IntentClassifier."""
    
    def test_gm_routes_action(self):
        """Test 'I attack the goblin' -> ACTION -> work."""
        mock_llm = MagicMock()
        # Mock classifier output
        mock_llm.invoke.return_value = AIMessage(content="ACTION")
        
        classifier = create_gm_classifier(mock_llm)
        
        state = GameState(messages=[HumanMessage(content="I attack the goblin")], rule_check_result="")
        
        # Run classifier
        new_state = classifier(state)
        
        assert new_state.rule_check_result == "ACTION"
        
        # Test routing decision
        route = gm_route_root(new_state)
        assert route == "work"
        
    def test_gm_routes_interaction(self):
        """Test 'Who are you?' -> INTERACTION -> chat."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = AIMessage(content="INTERACTION")
        
        classifier = create_gm_classifier(mock_llm)
        state = GameState(messages=[HumanMessage(content="Who are you?")], rule_check_result="")
        
        new_state = classifier(state)
        assert new_state.rule_check_result == "INTERACTION"
        
        route = gm_route_root(new_state)
        assert route == "chat"


class TestWriterIntentRouting:
    """Test the Writer Agent's IntentClassifier."""
    
    def test_writer_routes_drafting(self):
        """Test 'Draft chapter 1' -> ACTION -> work."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = AIMessage(content="ACTION")
        
        classifier = create_writer_classifier(mock_llm)
        
        # Check WriterState structure. 
        # Note: In writer_agent.py, we abuse 'critique_notes' for intent storage.
        state = WriterState(
            messages=[HumanMessage(content="Draft chapter 1")], 
            current_outline="",
            project_id="test",
            iteration_count=0,
            retrieved_lore="",
            draft_content="",
            critique_notes="",
            agent_role="writer"
        )
        
        new_state = classifier(state)
        assert new_state.critique_notes == "ACTION"
        
        route = writer_route_root(new_state)
        assert route == "work"
        
    def test_writer_routes_chat(self):
        """Test 'What do you think?' -> INTERACTION -> chat."""
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = AIMessage(content="INTERACTION")
        
        classifier = create_writer_classifier(mock_llm)
        
        state = WriterState(
            messages=[HumanMessage(content="What do you think?")],
            current_outline="",
            project_id="test",
            iteration_count=0,
            retrieved_lore="",
            draft_content="",
            critique_notes="",
            agent_role="writer"
        )
        
        new_state = classifier(state)
        assert new_state.critique_notes == "INTERACTION"
        
        route = writer_route_root(new_state)
        assert route == "chat"
