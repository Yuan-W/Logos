"""
Editor Node
===========
Post-processing guardrail for enforcing terminology consistency.
"""
import json
from typing import Optional, Any, Dict
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage
from langchain_core.language_models import BaseChatModel
from sqlalchemy.orm import Session

from backend.tools.glossary import TermRetriever

EDITOR_PROMPT = """You are a meticulous Proofreader and Editor.
Your ONLY job is to check the text for compliance with the provided Glossary.

Glossary (Strict Enforcement):
{glossary_json}

Instruction:
1. Review the input text.
2. If ANY term from the glossary is used incorrectly (or if a synonym is used instead of the official term), you MUST correct it.
3. Keep the writing style, tone, and language (Chinese) exactly the same. Only swap the terms.
4. If the text is already correct, return the string "PASS".
5. If changes are made, return the corrected text ONLY.
"""

def create_editor(llm: BaseChatModel, session: Session):
    """
    Create an Editor node that enforces glossary terms.
    
    Args:
        llm: Fast LLM (e.g. gpt-4o-mini or gemini-flash)
        session: DB Session for vocabulary lookup
    """
    retriever = TermRetriever(session)
    
    # Text Splitter Helper
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    
    # Simple recursive splitter for sentence-level semantic search
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=300,
        chunk_overlap=50,
        separators=["\n\n", "\n", "。", "！", "？", ".", "!", "?", " "]
    )
    
    def editor(state: Any) -> Any:
        # 1. Check Strict Mode
        strict_mode = getattr(state, "strict_mode", False)
        
        if not strict_mode:
            return state
            
        # 2. Extract Last Message
        messages = state.messages
        if not messages:
            return state
            
        last_msg = messages[-1]
        text_content = ""
        
        if isinstance(last_msg, BaseMessage):
            text_content = last_msg.content
        elif isinstance(last_msg, dict):
            text_content = last_msg.get("content", "")
            
        if not text_content:
            return state

        # 3. Retrieve Relevant Terms (Chunk-based)
        scopes = getattr(state, "active_scopes", [])
        if not scopes:
             scopes = ["global:trpg", "global:writing"]
             
        # Split text into semantic chunks for better retrieval accuracy
        chunks = text_splitter.split_text(text_content)
        
        # Limit chunks to avoid explosive DB calls (e.g. max 5 chunks for a response)
        # If response is huge, we might process only first/last or random subsample? 
        # For now, process all but limit total terms.
        
        collected_terms = {}
        for chunk in chunks[:10]: # Safety cap
            terms = retriever.fetch_terms(scopes, chunk, limit=3) # Fetch top 3 per chunk
            collected_terms.update(terms)
            
        if not collected_terms:
            return state
            
        # 4. LLM Correction
        glossary_json = json.dumps(collected_terms, ensure_ascii=False)
        
        prompt = EDITOR_PROMPT.format(glossary_json=glossary_json)
        
        response = llm.invoke([
            SystemMessage(content=prompt),
            HumanMessage(content=text_content)
        ])
        
        corrected_text = response.content.strip()
        
        if corrected_text == "PASS":
            return state
             
        # 5. Update State
        if isinstance(last_msg, BaseMessage):
            new_msg = type(last_msg)(content=corrected_text)
            state.messages[-1] = new_msg
            
            if hasattr(state, "draft_content"):
                state.draft_content = corrected_text
                
        return state
        
    return editor
