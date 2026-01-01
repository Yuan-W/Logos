"""
Deep Researcher Agent
=====================
RAG-heavy agent that performs query expansion, batch retrieval, and citation-based synthesis.
Powered by Shared RAG Engine.
Target: Document table.
"""

from typing import List, Any, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session
from langchain_core.language_models import BaseChatModel
from langchain_core.documents import Document as LangChainDocs
from langgraph.graph.state import CompiledStateGraph
from langchain_core.tools import tool
from sqlalchemy import text

from backend.database.models import Document, DocumentChunk
from backend.database.db_init import get_session
from backend.agents.rag_engine import create_rag_graph
from backend.utils.ingestion import get_embedding


# =============================================================================
# Configuration
# =============================================================================

RESEARCHER_SYSTEM_PROMPT = """You are a rigorous academic writer. 
Answer the user's question using ONLY the provided context.
CRITICAL: Every statement must be supported by a citation in the format [Doc ID: Page X].
If the context does not contain the answer, state that you do not know.
Do not make up information.
IMPORTANT: Please answer the user's question in CHINESE (Simplified Chinese).
请使用中文回答用户的问题。引用格式保持 `[Doc ID: Page X]` 不变。"""

# =============================================================================
# Retrieval Logic
# =============================================================================

@tool
def fetch_chart_data(query: str):
    """
    Search for structured data from Charts/Graphs in documents.
    Returns JSON data of the chart if found.
    """
    session = get_session()
    try:
        # Similar logic: Search DocumentChunk content + JSON filter
        sql = text("""
            SELECT stat_block FROM document_chunks
            WHERE content ILIKE :q 
            LIMIT 1
        """)
        result = session.execute(sql, {"q": f"%{query}%"}).scalar()
        
        if result:
            return str(result)
        return "No chart data found."
    finally:
        session.close()

def retrieve_documents(session: Session, queries: List[str], k: int = 3) -> List[LangChainDocs]:
    """Retrieve documents using cosine similarity via pgvector."""
    results = []
    
    for query in queries:
        query_vec = get_embedding(query)
        
        # 1. Search Standard Documents
        stmt = select(Document).order_by(
            Document.embedding.cosine_distance(query_vec)
        ).limit(k)
        docs = session.execute(stmt).scalars().all()
        
        for doc in docs:
            results.append(LangChainDocs(
                page_content=doc.chunk_content,
                metadata={"id": doc.id, "title": doc.title, "page": doc.source_page}
            ))
            
        # 2. Search DocumentChunks (Vision Extracted)
        stmt_chunks = select(DocumentChunk).order_by(
            DocumentChunk.embedding.cosine_distance(query_vec)
        ).limit(k)
        chunks = session.execute(stmt_chunks).scalars().all()
        
        for chunk in chunks:
            # Append stat_block info to content for Synthesis
            content_with_stats = f"{chunk.content}\n[Structured Data: {chunk.stat_block}]"
            results.append(LangChainDocs(
                page_content=content_with_stats,
                metadata={"id": f"chunk_{chunk.id}", "source": "Vision Extract", "type": "chunk"}
            ))
            
    return results


# =============================================================================
# Builder
# =============================================================================

def build_researcher_agent(llm: BaseChatModel, session: Session, checkpointer: Optional[Any] = None) -> CompiledStateGraph:
    """Build the Researcher Agent using the Shared RAG Engine."""
    
    def retrieve_wrapper(queries: List[str]) -> List[LangChainDocs]:
        return retrieve_documents(session, queries, k=3)
        
    return create_rag_graph(
        llm=llm,
        session=session,
        retrieve_fn=retrieve_wrapper,
        system_prompt=RESEARCHER_SYSTEM_PROMPT,
        role_name="Academic Researcher",
        checkpointer=checkpointer
    )
