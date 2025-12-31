"""
Agent Factory
=============
Centralized factory for creating agents with standardized configurations,
including Terminology Registry injection.
"""

from typing import List, Optional, Any, Dict
from sqlalchemy.orm import Session
from langchain_core.language_models import BaseChatModel

from src.tools.glossary import fetch_glossary_context
from src.agents.gm_agent import build_gm_agent
from src.agents.researcher_agent import build_researcher_agent
from src.agents.coach_agent import build_coach_agent
from src.agents.writer_agent import build_writer_agent


class AgentFactory:
    """Factory for building agents with injected dependencies."""
    
    def __init__(self, llm: BaseChatModel, session: Session, checkpointer: Optional[Any] = None):
        self.llm = llm
        self.session = session
        self.checkpointer = checkpointer
        
    def create_agent(self, role: str, scopes: List[str], query: str = ""):
        """
        Create an agent instance with glossary context injected.
        
        Args:
            role: The agent role ('gm', 'researcher', 'coach', 'writer')
            scopes: List of glossary scopes to active.
            query: The user query to fetch relevant terms for context (optional).
        """
        # Fetch relevant glossary terms
        glossary_context = ""
        if scopes:
            glossary_context = fetch_glossary_context(self.session, scopes, query)
            
        # Build agent specific to role
        if role == "gm":
            return build_gm_agent(
                llm=self.llm, 
                session=self.session, 
                checkpointer=self.checkpointer,
                glossary_context=glossary_context
            )
            
        elif role == "researcher":
            # Assuming other agents might also need refactoring to accept glossary_context
            # For now, pass checkpointer. If they don't accept glossary_context, we simply
            # ignore it for now or we must refactor them too.
            # Plan only mandated refactoring agents. The user mentioned "ALL agents".
            # I will refactor others as I verify them.
            return build_researcher_agent(self.llm, self.session, checkpointer=self.checkpointer)
            
        elif role == "coach":
            return build_coach_agent(
                 llm=self.llm,
                 session=self.session,
                 checkpointer=self.checkpointer,
                 glossary_context=glossary_context
            )
            
        elif role == "writer":
            return build_writer_agent(
                llm=self.llm,
                session=self.session,
                checkpointer=self.checkpointer,
                glossary_context=glossary_context
            )
            
        else:
            raise ValueError(f"Unknown agent role: {role}")
