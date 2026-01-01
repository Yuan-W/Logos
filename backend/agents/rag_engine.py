"""
Shared RAG Engine
=================
Generic factory for creating Search-Expand-Retrieve-Synthesize agents.
Used by Researcher (Documents) and Code Coach (CodeSnippets).
"""

from typing import Callable, List, Optional, Any
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.documents import Document as LangChainDocs
from langchain_core.language_models import BaseChatModel
from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.orm import Session

from backend.graph.state import ResearchState
from backend.agents.nodes.editor import create_editor

# =============================================================================
# Generic Node Creators
# =============================================================================

def create_query_expander(llm: BaseChatModel, role_prompt: str = ""):
    """Node: Breaks complex questions into sub-queries."""
    
    base_prompt = """Break down the user's question into 3-5 distinct search queries to maximize information retrieval.
Return ONLY the queries, one per line. Do not number them."""
    
    full_prompt = f"{role_prompt}\n\n{base_prompt}" if role_prompt else base_prompt

    def query_expander(state: ResearchState) -> ResearchState:
        messages = state.messages
        if not messages:
            return state
            
        last_message = messages[-1].content
        
        prompt = [
            SystemMessage(content=full_prompt),
            HumanMessage(content=f"User Question: {last_message}")
        ]
        
        response = llm.invoke(prompt)
        queries = [q.strip() for q in response.content.split("\n") if q.strip()]
        
        state.search_queries = queries[:5]
        return state

    return query_expander


def create_generic_retriever(retrieve_fn: Callable[[List[str]], List[LangChainDocs]]):
    """
    Node: Executes sub-queries using the provided retrieval function.
    
    retrieve_fn: A function that takes a list of query strings and returns a list of LangChain Documents.
    """
    
    def batch_retrieve(state: ResearchState) -> ResearchState:
        queries = state.search_queries
        if not queries:
            return state
            
        # Execute retrieval
        all_docs = retrieve_fn(queries)
        
        # Helper to dedup by ID if present, otherwise blindly append? 
        # Assuming retrieve_fn handles some logic, but let's dedup by page_content or id metadata here for safety.
        # But for now, trust the retrieve_fn or simple dedup.
        
        unique_docs = {}
        for doc in all_docs:
            # Use metadata ID if available, else hash content
            doc_id = doc.metadata.get("id")
            if doc_id:
                if doc_id not in unique_docs:
                    unique_docs[doc_id] = doc
            else:
                # Fallback
                unique_docs[hash(doc.page_content)] = doc
                
        state.retrieved_docs = list(unique_docs.values())
        return state
        
    return batch_retrieve


def create_synthesizer(llm: BaseChatModel, system_prompt: str):
    """Node: Generates answer with citations."""
    
    def synthesize(state: ResearchState) -> ResearchState:
        docs = state.retrieved_docs
        query = state.messages[-1].content
        
        # Format context
        context_str = ""
        for i, doc in enumerate(docs):
            # Try to get citation info
            source = doc.metadata.get("source", "Unknown")
            page = doc.metadata.get("page", "?")
            file_path = doc.metadata.get("file_path", "")
            
            # Format based on available metadata (Generic)
            citation_info = f"ID: {doc.metadata.get('id', i)}"
            if file_path:
                line = doc.metadata.get("line", "")
                citation_info = f"File: {file_path} Line: {line}"
            elif page != "?":
                citation_info = f"Page: {page}"
                
            context_str += f"--- Source ({citation_info}) ---\n{doc.page_content}\n\n"
            
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
# Graph Factory
# =============================================================================

def create_rag_graph(
    llm: BaseChatModel,
    session: Session,
    retrieve_fn: Callable[[List[str]], List[LangChainDocs]],
    system_prompt: str,
    role_name: str = "researcher", # For logging or prompt customization
    checkpointer: Optional[Any] = None
) -> CompiledStateGraph:
    """
    Builds a generic RAG agent.
    
    Flow: Expand -> Retrieve -> Synthesize -> Editor -> END
    """
    
    # Create nodes
    query_expander = create_query_expander(llm, role_prompt=f"You are a {role_name}.")
    retriever_node = create_generic_retriever(retrieve_fn)
    synthesizer = create_synthesizer(llm, system_prompt)
    editor = create_editor(llm, session)
    
    # Build graph
    graph = StateGraph(ResearchState)
    
    graph.add_node("expand", query_expander)
    graph.add_node("retrieve", retriever_node)
    graph.add_node("synthesize", synthesizer)
    graph.add_node("editor", editor)
    
    # Edges
    graph.set_entry_point("expand")
    graph.add_edge("expand", "retrieve")
    graph.add_edge("retrieve", "synthesize")
    graph.add_edge("synthesize", "editor")
    graph.add_edge("editor", END)
    
    return graph.compile(checkpointer=checkpointer)
