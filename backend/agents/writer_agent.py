"""
Writer Agent
============
Reflexion-based agent for long-form content generation (Novelist & Screenwriter).

Nodes:
1. LoreRetriever: Fetches context from StoryBible
2. Drafter: Generates text (Dynamic prompts for Novel text vs Script)
3. Critic: Checks consistency and logic
4. Reviser: Rewrites if needed (Conditional Loop)
5. LoreExtractor: Updates StoryBible with new entities/facts
"""

from typing import Literal, Annotated, Optional, Any
import json

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.language_models import BaseChatModel
from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from langchain_openai import OpenAIEmbeddings
import os

from backend.graph.state import WriterState
from backend.database.models import StoryBible
from backend.database.db_init import get_session
from backend.agents.nodes.editor import create_editor


# =============================================================================
# System Prompts
# =============================================================================

NOVELIST_PROMPT = """You are a master Novelist.
Write a scene based on the Outline and Lore provided.

Style Guidelines:
- Focus on sensory details (sight, sound, smell).
- Show, don't tell.
- Maintain deep POV.
- Use prose suitable for a high-quality published novel.
- LANGUAGE: You MUST write the content in CHINESE (Simplified Chinese), unless the user explicitly asks for English. 请使用优美的中文进行创作。

Format:
- Standard prose.
"""

SCREENWRITER_PROMPT = """You are a Hollywood Screenwriter.
Write a scene based on the Outline and Lore provided.

Format: FOUNTAIN / SCREENPLAY
- Use proper Sluglines (INT. LOCATION - DAY)
- Action lines must be present tense and visual.
- Dialogue centered with character names.
- Keep descriptions punchy and visual.
- LANGUAGE: Scene headings and Character names can be English or Chinese, but Dialogue and Action should be CHINESE (Simplified Chinese). 请使用中文编写剧本内容。
"""

CRITIC_PROMPT = """You are a ruthless Continuity Editor.
Review the draft against the provided Lore.

Check for:
1. Logic gaps (e.g. Character A is dead but talking)
2. Lore contradictions
3. Tone consistency

Output JSON ONLY:
{
    "status": "Approve" OR "Critique Feedback",
    "feedback": "Details if rejected, else empty"
}
"""

LORE_EXTRACTOR_PROMPT = """Analyze the final text. 
Identify NEW entities (Characters, Locations, Items) or significant updates to existing ones.

Output JSON list:
[
    {
        "entity_name": "Name",
        "entity_type": "character/location/item/event",
        "description": "Description of the entity based on text",
        "relations": {"allies": [], "enemies": []}
    }
]
If nothing new, return empty list [].
"""

WRITER_PERSONA_PROMPT = """You are the Co-Author / Editor.
You are NOT writing the story right now. You are discussing the project, tone, or style with the user.
Do NOT generate draft content here. Answer questions about the writing process or your capabilities.

Persona:
- Analytical and constructively critical.
- Professional but collaborative.
- When asked "What do you think?", provide analysis of the existing outline/draft, not a continuation.
- Start responses with "Analyzer:" or "Editor:" flavor.

User Query: {query}
"""

INTENT_ROUTER_PROMPT = """Classify the user's message.
TYPE A: ACTION (Drafting, Editing, "Write chapter 1", "Critique this", "Add a character")
TYPE B: INTERACTION (Meta-discussion: "What do you think of this idea?", "Who are you?", "Change the tone to dark")

Output ONLY: ACTION or INTERACTION.

Message: {message}"""


# =============================================================================
# Helper
# =============================================================================

embedding_model = OpenAIEmbeddings(
    model="text-embedding-3-small",
    openai_api_key=os.getenv("OPENAI_API_KEY", "sk-litellm-master-key"),
    openai_api_base=os.getenv("LITELLM_URL", "http://litellm:4000/v1")
)

def retrieve_lore(query: str, project_id: str, session: Session, k: int = 3) -> str:
    """Retrieve lore from StoryBible using vector search."""
    if not query:
        return ""
        
    query_vec = embedding_model.embed_query(query)
    
    stmt = select(StoryBible).where(
        StoryBible.project_id == project_id
    ).order_by(
        StoryBible.embedding.cosine_distance(query_vec)
    ).limit(k)
    
    results = session.execute(stmt).scalars().all()
    
    lore_text = []
    for r in results:
        lore_text.append(f"[{r.entity_type.upper()}] {r.entity_name}: {r.description}")
        
    return "\n".join(lore_text)


# =============================================================================
# Nodes
# =============================================================================

def create_lore_retriever(session: Session):
    def lore_retriever(state: WriterState) -> WriterState:
        outline = state.current_outline
        project_id = state.project_id
        
        # Extract keywords for search from outline (simplified: use whole outline)
        lore = retrieve_lore(outline, project_id, session)
        
        state.retrieved_lore = lore
        return state
    return lore_retriever


def create_drafter(llm: BaseChatModel, glossary_context: str = ""):
    def drafter(state: WriterState) -> WriterState:
        # Determine Role logic
        role = "novelist"
        
        # Check explicit agent role from state (injected by main.py)
        if state.agent_role == "screenwriter":
            role = "screenwriter"
        elif "screenplay" in state.current_outline.lower():
            role = "screenwriter"
            
        sys_prompt = SCREENWRITER_PROMPT if role == "screenwriter" else NOVELIST_PROMPT
        
        # Inject Glossary Context
        if glossary_context:
            sys_prompt += f"\n\n{glossary_context}"
            
        prompt = f"""LORE:\n{state.retrieved_lore}\n\nOUTLINE:\n{state.current_outline}\n\nPREVIOUS FEEDBACK: {state.critique_notes}"""
        
        messages = [
            SystemMessage(content=sys_prompt),
            HumanMessage(content=prompt)
        ]
        
        response = llm.invoke(messages)
        state.draft_content = response.content
        state.messages.append(AIMessage(content=response.content)) # Fix: Append to history
        state.iteration_count += 1
        return state
    return drafter


def create_critic(llm: BaseChatModel):
    def critic(state: WriterState) -> WriterState:
        prompt = f"""LORE:\n{state.retrieved_lore}\n\nDRAFT:\n{state.draft_content}"""
        
        response = llm.invoke([
            SystemMessage(content=CRITIC_PROMPT),
            HumanMessage(content=prompt)
        ])
        
        try:
            content = response.content.replace("```json", "").replace("```", "").strip()
            result = json.loads(content)
        except:
            result = {"status": "Approve", "feedback": ""}
            
        if result.get("status") == "Critique Feedback":
            state.critique_notes = result.get("feedback", "")
        else:
            state.critique_notes = "Approve"
            
        return state
    return critic


def create_reviser():
    # Pass-through node, the actual feedback is in state.critique_notes
    # Logic is handled by the Drafter using previous feedback
    def reviser(state: WriterState) -> WriterState:
        return state
    return reviser


def create_lore_extractor(llm: BaseChatModel, session: Session):
    def lore_extractor(state: WriterState) -> WriterState:
        response = llm.invoke([
            SystemMessage(content=LORE_EXTRACTOR_PROMPT),
            HumanMessage(content=state.draft_content)
        ])
        
        try:
            content = response.content.replace("```json", "").replace("```", "").strip()
            entities = json.loads(content)
        except:
            entities = []
            
        project_id = state.project_id
        
        for entity in entities:
            # Generate embedding
            desc = entity.get("description", "")
            if not desc: continue
            
            embedding = embedding_model.embed_query(desc)
            
            # Upsert logic (simplistic: insert always for now, or check existence)
            # For StoryBible we might want to append?
            # Let's just insert new records.
            new_entity = StoryBible(
                project_id=project_id,
                entity_name=entity.get("entity_name", "Unknown"),
                entity_type=entity.get("entity_type", "misc"),
                description=desc,
                embedding=embedding,
                relations=entity.get("relations", {})
            )
            session.add(new_entity)
            
        if entities:
            session.commit()
            
        return state
    return lore_extractor

def create_intent_classifier(llm: BaseChatModel):
    def classifier(state: WriterState) -> WriterState:
        # We reuse the same logic pattern, but WriterState has no 'rule_check_result'.
        # We need a place to store intent. WriterState has 'critique_notes' or we can add a transient field?
        # Let's override 'critique_notes' temporarily if needed, or rely on distinct return value in ConditionalEdge 
        # (LangGraph ConditionalEdge functions get the state, so we need to store it in state).
        # WriterState usually has 'current_outline'.
        # Let's add a 'temp_intent' to the dict returned if we could... but we are using Pydantic-like object or TypedDict?
        # WriterState is likely a Class or TypedDict. Let's check backend/graph/state.py or import.
        # It is imported: `from backend.graph.state import WriterState`
        # Assuming we can't easily change schema. Let's re-purpose 'critique_notes' as the "Scratchpad".
        
        messages = state.messages
        last_msg = messages[-1].content if messages else ""
        
        response = llm.invoke([
            SystemMessage(content=INTENT_ROUTER_PROMPT.format(message=last_msg))
        ])
        
        classification = response.content.strip().upper()
        state.critique_notes = classification # Abuse this field for routing
        return state
    return classifier

def create_persona_chat(llm: BaseChatModel):
    def persona_chat(state: WriterState) -> WriterState:
        messages = state.messages
        last_msg = messages[-1].content if messages else ""
        
        response = llm.invoke([
            SystemMessage(content=WRITER_PERSONA_PROMPT.format(query=last_msg))
        ])
        
        state.messages.append(AIMessage(content=response.content))
        return state
    return persona_chat

def route_root(state: WriterState) -> str:
    # Check 'critique_notes' which holds the classification
    intent = state.critique_notes
    if intent == "ACTION":
        return "work"
    return "chat"


# =============================================================================
# Graph
# =============================================================================

def build_writer_agent(llm: BaseChatModel, session: Session, checkpointer: Optional[Any] = None, glossary_context: str = "") -> CompiledStateGraph:
    """
    Build Writer Agent Graph.
    
    Flow:
    LoreRetriever -> Drafter -> Critic -> [Check]
       -> (Needs Revision & Iter < 2) -> Reviser -> Drafter
       -> (Approved or Max Iter) -> LoreExtractor -> END
    """
    
    graph = StateGraph(WriterState)
    
    # Nodes
    graph.add_node("classifier", create_intent_classifier(llm))
    graph.add_node("persona_chat", create_persona_chat(llm))
    
    graph.add_node("retrieve", create_lore_retriever(session))
    graph.add_node("draft", create_drafter(llm, glossary_context))
    graph.add_node("editor", create_editor(llm, session))
    graph.add_node("critic", create_critic(llm))
    graph.add_node("revise", create_reviser())
    graph.add_node("extract", create_lore_extractor(llm, session))
    
    # Edges
    graph.set_entry_point("classifier")
    
    graph.add_conditional_edges(
        "classifier",
        route_root,
        {
            "work": "retrieve",
            "chat": "persona_chat"
        }
    )
    
    graph.add_edge("persona_chat", END)
    
    # Work Graph
    graph.add_edge("retrieve", "draft")
    graph.add_edge("draft", "editor")
    graph.add_edge("editor", "critic")
    
    def revision_check(state: WriterState):
        if state.critique_notes != "Approve" and state.iteration_count < 2:
            return "revise"
        return "extract"
        
    graph.add_conditional_edges(
        "critic",
        revision_check,
        {
            "revise": "revise",
            "extract": "extract"
        }
    )
    
    graph.add_edge("revise", "draft")
    graph.add_edge("extract", END)
    
    return graph.compile(checkpointer=checkpointer)
