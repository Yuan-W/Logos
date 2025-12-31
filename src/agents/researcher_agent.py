"""
Deep Researcher Agent
=====================
RAG-heavy agent that performs query expansion, batch retrieval, and citation-based synthesis.

Search -> Expand -> Retrieve -> Synthesize
"""

import os
from typing import List, Annotated, Optional, Any
from typing_extensions import TypedDict

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.language_models import BaseChatModel
from langchain_core.documents import Document as LangChainDocs
from langchain_openai import OpenAIEmbeddings
from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from src.graph.state import ResearchState
from src.database.models import Document
from src.database.db_init import get_session


# =============================================================================
# Setup
# =============================================================================

embedding_model = OpenAIEmbeddings(
    model="text-embedding-3-small",
    openai_api_key=os.getenv("OPENAI_API_KEY", "sk-litellm-master-key"),
    openai_api_base=os.getenv("OPENAI_API_BASE_URL", "http://localhost:4000/v1")
)

# =============================================================================
# Tools & Helpers
# =============================================================================

def retrieve_documents(query: str, session: Session, k: int = 3) -> List[Document]:
    """
    Retrieve documents using cosine similarity via pgvector.
    
    Args:
        query: Search string
        session: Database session
        k: Number of documents to retrieve per query
        
    Returns:
        List of Document models
    """
    # Generate embedding for query
    query_embedding = embedding_model.embed_query(query)
    
    # Cosine similarity search (1 - cosine distance) implies ordering by distance ASC
    # In pgvector: <=> is cosine distance, <-> is L2 distance, <#> is inner product
    # For normalized vectors (OpenAI), larger inner product = closer.
    # But usually we use the distance operator for ORDER BY.
    # pgvector 0.5.0+ supports cosine distance nicely with <=>
    
    stmt = select(Document).order_by(
        Document.embedding.cosine_distance(query_embedding)
    ).limit(k)
    
    results = session.execute(stmt).scalars().all()
    return list(results)


# =============================================================================
# Node Functions
# =============================================================================

def create_query_expander(llm: BaseChatModel):
    """Node: Breaks complex questions into sub-queries."""
    
    system_prompt = """You are an expert researcher. 
Break down the user's question into 3-5 distinct search queries to maximize information retrieval.
Return ONLY the queries, one per line. Do not number them."""

    def query_expander(state: ResearchState) -> ResearchState:
        messages = state.messages
        if not messages:
            return state
            
        last_message = messages[-1].content
        
        prompt = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"User Question: {last_message}")
        ]
        
        response = llm.invoke(prompt)
        queries = [q.strip() for q in response.content.split("\n") if q.strip()]
        
        # Ensure we don't have too many
        state.search_queries = queries[:5]
        return state

    return query_expander


def create_batch_retriever(session: Session):
    """Node: Executes all sub-queries against Postgres."""
    
    def batch_retrieve(state: ResearchState) -> ResearchState:
        queries = state.search_queries
        if not queries:
            return state
            
        all_docs = []
        seen_ids = set()
        
        for query in queries:
            docs = retrieve_documents(query, session, k=3)
            for doc in docs:
                if doc.id not in seen_ids:
                    # Convert to LangChain Document format for easier handling
                    lc_doc = LangChainDocs(
                        page_content=doc.chunk_content,
                        metadata={
                            "id": doc.id,
                            "title": doc.title,
                            "page": doc.source_page
                        }
                    )
                    all_docs.append(lc_doc)
                    seen_ids.add(doc.id)
        
        state.retrieved_docs = all_docs
        return state
        
    return batch_retrieve


def create_rerank_filter():
    """Node: Deduplicates and filters (simplified pass-through for now)."""
    
    def rerank_filter(state: ResearchState) -> ResearchState:
        # In a real system, we might use a Cross-Encoder here.
        # For now, we rely on the vector distance (already somewhat sorted).
        # We just trim if too many docs.
        
        docs = state.retrieved_docs
        # Keep top 10 max
        state.retrieved_docs = docs[:10]
        return state
        
    return rerank_filter


def create_synthesizer(llm: BaseChatModel):
    """Node: Generates answer with citations."""
    
    system_prompt = """You are a rigorous academic writer. 
Answer the user's question using ONLY the provided context.
CRITICAL: Every statement must be supported by a citation in the format [Doc ID: Page X].
If the context does not contain the answer, state that you do not know.
Do not make up information.
IMPORTANT: Please answer the user's question in CHINESE (Simplified Chinese).
请使用中文回答用户的问题。引用格式保持 `[Doc ID: Page X]` 不变。"""

    def synthesize(state: ResearchState) -> ResearchState:
        docs = state.retrieved_docs
        query = state.messages[-1].content
        
        # Format context
        context_str = ""
        for i, doc in enumerate(docs):
            meta = doc.metadata
            context_str += f"--- Document {meta['id']} (Page {meta['page']}) ---\n{doc.page_content}\n\n"
            
        prompt = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Context:\n{context_str}\n\nQuestion: {query}")
        ]
        
        response = llm.invoke(prompt)
        
        state.draft_answer = response.content
        state.messages.append(AIMessage(content=response.content))
        return state
        
    return synthesize


# =============================================================================
# Graph Builder
# =============================================================================

def build_researcher_agent(llm: BaseChatModel, session: Session, checkpointer: Optional[Any] = None) -> CompiledStateGraph:
    """
    Build the Researcher Agent graph.
    
    Flow: START -> QueryExpander -> BatchRetrieve -> RerankFilter -> Synthesize -> END
    """
    
    # Create nodes
    query_expander = create_query_expander(llm)
    batch_retriever = create_batch_retriever(session)
    rerank_filter = create_rerank_filter()
    synthesizer = create_synthesizer(llm)
    
    # Build graph
    graph = StateGraph(ResearchState)
    
    graph.add_node("expand", query_expander)
    graph.add_node("retrieve", batch_retriever)
    graph.add_node("rerank", rerank_filter)
    graph.add_node("synthesize", synthesizer)
    
    # Edges (Linear flow)
    graph.set_entry_point("expand")
    graph.add_edge("expand", "retrieve")
    graph.add_edge("retrieve", "rerank")
    graph.add_edge("rerank", "synthesize")
    graph.add_edge("synthesize", END)
    
    return graph.compile(checkpointer=checkpointer)
