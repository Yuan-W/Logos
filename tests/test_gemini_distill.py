"""
Test Gemini-Distill Engine (Vision and Data Retrieval)
======================================================
Verifies:
1. GeminiIngestor logic (Mocking Vision API response).
2. Agent Tools (lookup_stats, retrieval of structured data).
"""

import pytest
import json
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session
from langchain_core.messages import AIMessage

from src.ingest.engine import GeminiIngestor
from src.database.models import RuleBookChunk, DocumentChunk
from src.database.db_init import get_session
from src.agents.gm_agent import lookup_stats
from src.agents.researcher_agent import fetch_chart_data

@pytest.fixture
def session():
    sess = get_session()
    # Cleanup
    sess.query(RuleBookChunk).delete()
    sess.query(DocumentChunk).delete()
    sess.commit()
    yield sess
    sess.close()

def test_ingestion_logic_mocked(session):
    """
    Test that GeminiIngestor correctly processes a mocked Vision response
    and saves RuleBookChunk with JSONB stats.
    """
    # Mock mocks
    mock_pdf_convert = MagicMock()
    # Return 1 dummy image
    mock_image = MagicMock()
    mock_pdf_convert.return_value = [mock_image]
    
    # Mock LLM response
    mock_vision_resp = AIMessage(content=json.dumps({
        "content": "# Goblin\nA small green creature.",
        "stat_blocks": [
            {"name": "Goblin", "hp": 7, "ac": 15, "type": "monster"}
        ]
    }))
    
    with patch("src.ingest.engine.convert_from_path", mock_pdf_convert):
        with patch("src.ingest.engine.vision_llm") as mock_llm:
            mock_llm.invoke.return_value = mock_vision_resp
            
            ingestor = GeminiIngestor(session)
            # Use dummy path; convert_from_path is mocked so it won't care
            ingestor.process_file("dummy_rulebook.pdf", flavor="trpg")
            
            # Verify DB
            chunk = session.query(RuleBookChunk).first()
            assert chunk is not None
            assert chunk.content == "# Goblin\nA small green creature."
            # Verify JSONB
            stats = chunk.stat_block
            # Note: Engine wraps list in {"items": [...]}
            assert "items" in stats
            items = stats["items"]
            assert len(items) == 1
            assert items[0]["name"] == "Goblin"
            assert items[0]["hp"] == 7
            
            print("Ingestion Verification Passed.")

def test_agent_tool_retrieval(session):
    """
    Test that agent tools can find the data we just ingested.
    """
    # Setup Data
    chunk = RuleBookChunk(
        content="The Goblin King waits.",
        embedding=[0.1]*768,
        stat_block={"items": [{"name": "Goblin King", "hp": 50, "ac": 18}]}
    )
    session.add(chunk)
    
    doc_chunk = DocumentChunk(
        content="Sales Report 2025",
        embedding=[0.2]*768,
        stat_block={"items": [{"label": "Q1 Sales", "data": [100, 200]}]}
    )
    session.add(doc_chunk)
    session.commit()
    
    # Test GM Tool: lookup_stats
    # Note: lookup_stats is a generic tool. Need to insure context manager uses correct session factory if it calls get_session() inside.
    # But for test, we rely on the DB being committed.
    
    # The tool implementation uses ILIKE on content.
    # Query "Goblin King"
    # Note: The tool creates its OWN session via get_session(). Use generic one to verify shared state.
    
    res = lookup_stats.invoke("Goblin King")
    print(f"GM Tool Result: {res}")
    assert "Goblin King" in res
    assert "50" in res # HP
    
    # Test Researcher Tool: fetch_chart_data
    res2 = fetch_chart_data.invoke("Sales Report")
    print(f"Researcher Tool Result: {res2}")
    assert "Q1 Sales" in res2
