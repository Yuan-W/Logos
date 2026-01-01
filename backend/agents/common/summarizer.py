"""
Common Summarizer Node
======================
Shared logic for compressing conversation history.
"""

from typing import Dict, Any, List
from langchain_core.messages import BaseMessage, SystemMessage, RemoveMessage, HumanMessage, AIMessage
from langchain_core.language_models import BaseChatModel
from backend.graph.state import BaseState

SUMMARIZER_PROMPT = """Create a concise summary of the following conversation interaction.
Focus on key facts, decisions, and current context.
Existing Summary: {existing_summary}

New Interaction to Merge:
{new_lines}

Return ONLY the updated summary text.
LANGUAGE: Please use CHINESE (Simplified Chinese)."""


def create_summarizer(llm: BaseChatModel):
    """
    Creates a summarizer node that compresses history if it exceeds threshold.
    """
    
    def summarize_conversation(state: BaseState) -> Dict[str, Any]:
        """
        Summarize conversation if messages > 20.
        Compresses the oldest 10 messages into 'conversation_summary'.
        """
        messages = state.messages
        # Thresholds
        MAX_MESSAGES = 20
        COMPRESS_COUNT = 10
        
        if len(messages) <= MAX_MESSAGES:
            return {}
            
        # Select messages to summarize (excluding the very latest ones to keep context fresh)
        # We summarize the oldest batch.
        to_summarize = messages[:COMPRESS_COUNT]
        
        # Format for LLM
        summary_text = state.conversation_summary
        new_lines = "\n".join([f"{m.type}: {m.content}" for m in to_summarize])
        
        prompt = SUMMARIZER_PROMPT.format(
            existing_summary=summary_text,
            new_lines=new_lines
        )
        
        response = llm.invoke([
            SystemMessage(content=prompt)
        ])
        
        new_summary = response.content
        
        # Prepare delete operations
        delete_ops = [RemoveMessage(id=m.id) for m in to_summarize]
        
        return {
            "conversation_summary": new_summary,
            "messages": delete_ops
        }
        
    return summarize_conversation
