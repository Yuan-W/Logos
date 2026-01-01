"""
Test Semantic Editor Capabilities
=================================
Verifies that the Editor node can:
1. Retrieve terms based on semantic similarity (Simulated via 'upsert_term')
2. Rewrite text using the retrieved glossary.
"""

import pytest
from unittest.mock import MagicMock
from langchain_core.messages import AIMessage, HumanMessage

# Import SUT
from backend.tools.glossary import upsert_term, TermRetriever
from backend.agents.nodes.editor import create_editor
from backend.database.models import TermRegistry
from backend.graph.state import BaseState

# We need a real DB session for this to test pgvector, 
# but for unit testing in CI/CD we might mocking. 
# However, the user asked for "Verification", assuming access to the dev environment.
from backend.database.db_init import get_session

@pytest.fixture
def session():
    sess = get_session()
    yield sess
    sess.close()

def test_semantic_upsert_and_retrieval(session):
    """
    Test that 'upsert_term' creates a record and 'editor' retrieves it 
    even with inexact matching (Semantic).
    """
    # 1. Setup Data: "Fireball" -> "火球术" with aliases
    upsert_term(
        session=session,
        scope="test:semantic",
        term="火球术",
        definition="法师的基础火焰攻击技能",
        aliases=["大火球", "火焰飞弹"]
    )
    
    # 2. Check Retrieval independently first
    retriever = TermRetriever(session)
    # Query with strict non-exact text: "法师扔出了一个炽热的火球" (Mage threw a scorching fireball)
    # "火球" is close to "大火球" alias or "火球术" term.
    query = "法师扔出了一个炽热的球体" # "Scorching Sphere" - trying to rely on vector
    
    terms = retriever.fetch_terms(["test:semantic"], query)
    print(f"Retrieved Terms for '{query}': {terms}")
    
    assert "火球术" in terms, "Failed to retrieve '火球术' via semantic search for '炽热的球体'"

def test_editor_rewrite_logic(session):
    """
    Test the full Editor Node flow with chunking.
    """
    # Mock LLM to avoid cost, but verify prompt contained the term
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(content="法师扔出了一个火球术。")
    
    editor_node = create_editor(mock_llm, session)
    
    # State with Strict Mode
    state = BaseState(
        messages=[HumanMessage(content="法师扔出了一个大火球。")],
        strict_mode=True,
        active_scopes=["test:semantic"]
    )
    
    # Run
    new_state = editor_node(state)
    
    # Verify LLM was called
    args, _ = mock_llm.invoke.call_args
    prompts = args[0] # List[BaseMessage]
    system_prompt_content = prompts[0].content
    
    print(f"System Prompt Payload:\n{system_prompt_content}")
    
    # The JSON in the prompt should contain "火球术" because retrieval (using real DB) should have found it
    assert "火球术" in system_prompt_content
    # The output should be updated
    assert new_state.messages[-1].content == "法师扔出了一个火球术。"
