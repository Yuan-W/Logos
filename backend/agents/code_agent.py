"""
Code Coach Agent
================
RAG-based agent for coding assistance using the Shared RAG Engine.
Target: CodeSnippet table.
Role: Senior Staff Engineer.
"""

from typing import List, Any, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session
from langchain_core.language_models import BaseChatModel
from langchain_core.documents import Document as LangChainDocs
from langgraph.graph.state import CompiledStateGraph

from backend.database.models import CodeSnippet
from backend.agents.rag_engine import create_rag_graph
from backend.utils.ingestion import get_embedding


# =============================================================================
# Configuration
# =============================================================================

CODER_SYSTEM_PROMPT = """You are a Senior Staff Engineer.
Your goal is to provide high-quality, efficient, and robust code solutions.

Instructions:
1. Always review the provided Code Snippets context before answering.
2. If the context contains relevant code, USE IT.
3. When suggesting fixes or new code, use valid Markdown code blocks with language tags (e.g., ```python).
4. Do not be conversational. Be technical and precise.
5. If the user asks for a specific algorithm or pattern, implement it using standard best practices.

Citation Format:
Cite your sources as [File: path/to/file, Line: X] if applicable.
"""

# =============================================================================
# Retrieval Logic
# =============================================================================

def retrieve_code_snippets(session: Session, queries: List[str], k: int = 3) -> List[LangChainDocs]:
    """Retrieve code snippets based on semantic similarity."""
    results = []
    
    for query in queries:
        query_vec = get_embedding(query)
        
        # Search CodeSnippet table
        stmt = select(CodeSnippet).order_by(
            CodeSnippet.embedding.cosine_distance(query_vec)
        ).limit(k)
        
        snippets = session.execute(stmt).scalars().all()
        
        for snippet in snippets:
            # Format as Document
            doc = LangChainDocs(
                page_content=f"```{snippet.language}\n{snippet.code_block}\n```\nDescription: {snippet.description}",
                metadata={
                    "id": snippet.id,
                    "file_path": snippet.source_file,
                    "language": snippet.language,
                    "description": snippet.description
                }
            )
            results.append(doc)
            
    return results


# =============================================================================
# Builder
# =============================================================================

def build_code_agent(llm: BaseChatModel, session: Session, checkpointer: Optional[Any] = None) -> CompiledStateGraph:
    """Build the Code Coach agent using the Shared RAG Engine."""
    
    # Define retrieval wrapper
    def retrieve_wrapper(queries: List[str]) -> List[LangChainDocs]:
        return retrieve_code_snippets(session, queries, k=3)
        
    return create_rag_graph(
        llm=llm,
        session=session,
        retrieve_fn=retrieve_wrapper,
        system_prompt=CODER_SYSTEM_PROMPT,
        role_name="Senior Staff Engineer",
        checkpointer=checkpointer
    )
