"""
Agent Factory
=============
Centralized factory for creating agents with standardized configurations,
including Terminology Registry injection.
"""

from typing import List, Optional, Any, Dict
from sqlalchemy.orm import Session
from langchain_core.language_models import BaseChatModel

from backend.tools.glossary import fetch_glossary_context
from backend.agents.gm_agent import build_gm_agent
from backend.agents.researcher_agent import build_researcher_agent
from backend.agents.coach_agent import build_coach_agent
from backend.agents.writer_agent import build_writer_agent
from backend.agents.code_agent import build_code_agent
from backend.agents.lobby_agent import create_lobby_agent


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
            role: The agent role ('gm', 'researcher', 'coach', 'writer', 'coder')
            scopes: List of glossary scopes to active.
            query: The user query to fetch relevant terms for context (optional).
        """
        # Fetch relevant glossary terms
        glossary_context = ""
        if scopes:
            glossary_context = fetch_glossary_context(self.session, scopes, query)
            
        # Build agent specific to role
        if role in ["gm", "narrator", "rulekeeper"]:
            return build_gm_agent(
                llm=self.llm, 
                session=self.session, 
                checkpointer=self.checkpointer,
                glossary_context=glossary_context
            )
            
        elif role == "researcher":
            return build_researcher_agent(self.llm, self.session, checkpointer=self.checkpointer)
            
        elif role == "coder":
            return build_code_agent(self.llm, self.session, checkpointer=self.checkpointer)
            
        elif role in ["coach", "psychologist"]:
            return build_coach_agent(
                 llm=self.llm,
                 session=self.session,
                 checkpointer=self.checkpointer,
                 glossary_context=glossary_context
            )
            
        elif role in ["writer", "screenwriter"]:
            return build_writer_agent(
                llm=self.llm,
                session=self.session,
                checkpointer=self.checkpointer,
                glossary_context=glossary_context
            )
            
        elif role == "lobby":
            return create_lobby_agent(self.llm)

        else:
            raise ValueError(f"Unknown agent role: {role}")
