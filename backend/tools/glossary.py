"""
Glossary Tool
=============
Unified interface for fetching terminology definitions across different scopes.

Author: System Architect
"""

from typing import List, Dict, Any, Optional
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import select, or_, func
from sqlalchemy.orm import Session
from backend.database.models import TermRegistry
from backend.utils.ingestion import get_embedding


def upsert_term(session: Session, scope: str, term: str, definition: str, aliases: List[str] = None):
    """
    Insert or Update a term with Semantic Composite Embedding.
    
    Composite String: "Term (Alias1, Alias2): Definition"
    This ensures the vector captures synonyms and context.
    """
    if aliases is None:
        aliases = []
        
    # Create composite string for embedding
    alias_str = ", ".join(aliases)
    semantic_text = f"{term}"
    if alias_str:
        semantic_text += f" ({alias_str})"
    semantic_text += f": {definition}"
    
    embedding = get_embedding(semantic_text)
    
    # Upsert Logic
    stmt = insert(TermRegistry).values(
        scope=scope,
        term=term,
        definition=definition,
        aliases=aliases,
        embedding=embedding
    ).on_conflict_do_update(
        index_elements=['scope', 'term'], # Assuming unique constraint on scope+term (need to verify model)
        set_={
            "definition": definition,
            "aliases": aliases,
            "embedding": embedding,
            "updated_at": func.now()
        }
    )
    # Wait, simple insert might fail if constraint missing. 
    # models.py didn't verify UniqueConstraint on (scope, term).
    # Let's check models.py or use check-then-update logic for safety.
    
    existing = session.execute(
        select(TermRegistry).where(TermRegistry.scope == scope, TermRegistry.term == term)
    ).scalar_one_or_none()
    
    if existing:
        existing.definition = definition
        existing.aliases = aliases
        existing.embedding = embedding
    else:
        new_term = TermRegistry(
            scope=scope,
            term=term,
            definition=definition,
            aliases=aliases,
            embedding=embedding
        )
        session.add(new_term)
        
    session.commit()



class TermRetriever:
    """Retrieves terms from TermRegistry with scope prioritization."""
    
    def __init__(self, session: Session):
        self.session = session
        
    def fetch_terms(self, scopes: List[str], query: str, limit: int = 5) -> Dict[str, str]:
        """
        Fetch terms relevant to the query from specified scopes.
        
        Args:
            scopes: List of scopes [Global, Project, User]. Later scopes override earlier ones.
            query: The user input or context text to search for.
            limit: Max terms to retrieve per scope/query mix.
            
        Returns:
            Dict[term, definition] unified dictionary.
        """
        if not scopes or not query:
            return {}
            
        # 1. Keyword/Specific Term Search
        # If query contains specific terms, prioritize them.
        # This is simple for now, can be expanded to Keyword Extraction via LLM.
        
        # 2. Vector Search (Semantic)
        query_embedding = get_embedding(query)
        
        # We fetch results from DB
        # Note: pgvector supports order_by(TermRegistry.embedding.l2_distance(query_embedding))
        
        stmt = select(TermRegistry).where(
            TermRegistry.scope.in_(scopes)
        ).order_by(
            TermRegistry.embedding.l2_distance(query_embedding)
        ).limit(limit * 2) # Fetch extra to handle duplicate terms across scopes
        
        results = self.session.execute(stmt).scalars().all()
        
        # Process retrieval with priority
        # Scopes list order: [Base, Override1, Override2]
        # We want Override2 to win.
        
        scope_priority = {scope: i for i, scope in enumerate(scopes)}
        
        term_map: Dict[str, Any] = {}
        
        for record in results:
            term = record.term
            scope = record.scope
            
            # Distance check? (Optional, if library returns distance)
            # For now assume top-k is good.
            
            if term not in term_map:
                term_map[term] = record
            else:
                # Conflict resolution
                existing = term_map[term]
                if scope_priority.get(scope, -1) > scope_priority.get(existing.scope, -1):
                    term_map[term] = record
                    
        # Filter down to limit? Or return all relevant unique terms?
        # Returning top-k unique terms.
        
        final_terms = {}
        for term, record in term_map.items():
            final_terms[term] = record.definition
            
        return final_terms

    def format_glossary_prompt(self, terms: Dict[str, str]) -> str:
        """Format terms into a system prompt section."""
        if not terms:
            return ""
            
        lines = ["### TERMINOLOGY CONSTRAINTS"]
        lines.append("Context: Active Scopes")
        lines.append("Please adhere to the following definitions strictly:")
        
        for term, definition in terms.items():
            lines.append(f"- **{term}**: {definition}")
            
        return "\n".join(lines)


# Helper function for quick usage
def fetch_glossary_context(session: Session, scopes: List[str], query: str) -> str:
    retriever = TermRetriever(session)
    terms = retriever.fetch_terms(scopes, query)
    return retriever.format_glossary_prompt(terms)
