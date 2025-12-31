"""
TRPG Game Master Agent
======================
LangGraph workflow for the Dungeon Master persona.

Nodes:
1. StateLoader - Fetches game state from database
2. IntentParser - LLM decides if action requires rules/dice
3. ActionHandler - Executes rules lookup and dice rolls
4. Narrator - Generates story response
5. Saver - Commits updated state to database
"""

from typing import Annotated, Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.language_models import BaseChatModel
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.graph.state import GameState
from src.database.models import GameState as GameStateDB
from src.agents.tools import dice_roller, create_rule_lookup


# =============================================================================
# System Prompts
# =============================================================================

NARRATOR_SYSTEM_PROMPT = """You are the Game Master for a Blades in the Dark campaign.

SETTING: The haunted industrial city of Doskvol, where ghosts roam and criminal crews 
fight for territory in the perpetual dark. The sun is blocked by the shattered remnants 
of a cataclysm, and only electroplasmic barriers keep the city safe from the death-lands.

STYLE GUIDELINES:
- Use vivid, noir-inspired descriptions with gothic horror undertones
- Emphasize the oppressive atmosphere: soot, rain, gas lamps, shadows
- NPCs speak with working-class industrial accents and criminal slang
- Consequences are always looming—success comes with complications
- Reference the Spirit Wardens, Bluecoats, and faction politics naturally

DICE RESULTS INTERPRETATION:
- 6: Full success - describe a clean, impressive outcome
- 4-5: Partial success - succeed but with a complication or cost
- 1-3: Failure - things go wrong, introduce a new threat or setback

When describing actions:
1. Acknowledge what the player attempted
2. Incorporate any rule check results naturally
3. Describe the outcome cinematically
4. End with a hook or question to prompt next action

Current game state will be provided. Stay in character as the GM.

IMPORTANT: You MUST generate the narrative in CHINESE (Simplified Chinese).
保持中文回复。使用中文描述场景、动作和后果。但是游戏术语（如 "Blades in the Dark", "Action Roll"）可以保留英文或说明。"""

INTENT_PARSER_PROMPT = """Analyze the player's message and determine if it requires:
1. ACTION - Requires dice roll and/or rule check (combat, stealth, persuasion, etc.)
2. DIALOGUE - Roleplay conversation with NPCs or the world
3. QUERY - Player asking about game state, rules, or situation

Respond with ONLY one word: ACTION, DIALOGUE, or QUERY

Player message: {message}"""


# =============================================================================
# Node Functions
# =============================================================================

def create_state_loader(session: Session):
    """Create StateLoader node with database session."""
    
    def state_loader(state: GameState) -> GameState:
        """Fetch current game state from database."""
        user_id = state.user_id
        
        if not user_id:
            return state
        
        # Query game state
        stmt = select(GameStateDB).where(GameStateDB.session_id == user_id)
        db_state = session.execute(stmt).scalar_one_or_none()
        
        if db_state:
            state.current_hp = db_state.player_stats.get("hp", {})
            state.current_scene = db_state.current_scene
            state.active_npcs = list(db_state.npc_status.keys()) if db_state.npc_status else []
        
        return state
    
    return state_loader


def create_intent_parser(llm: BaseChatModel):
    """Create IntentParser node with LLM."""
    
    def intent_parser(state: GameState) -> GameState:
        """Determine player intent from message."""
        messages = state.messages
        
        if not messages:
            return state
        
        last_message = messages[-1]
        if not isinstance(last_message, HumanMessage):
            return state
        
        # Ask LLM to classify intent
        prompt = INTENT_PARSER_PROMPT.format(message=last_message.content)
        response = llm.invoke([HumanMessage(content=prompt)])
        
        intent = response.content.strip().upper()
        if intent not in ("ACTION", "DIALOGUE", "QUERY"):
            intent = "DIALOGUE"
        
        # Store intent for routing
        state.rule_check_result = intent
        return state
    
    return intent_parser


def create_action_handler(llm: BaseChatModel, session: Session):
    """Create ActionHandler node for processing game actions."""
    
    rule_lookup = create_rule_lookup(session)
    
    def action_handler(state: GameState) -> GameState:
        """Handle game actions with rules and dice."""
        messages = state.messages
        
        if not messages:
            return state
        
        last_message = messages[-1]
        if not isinstance(last_message, HumanMessage):
            return state
        
        action_text = last_message.content
        
        # 1. Look up relevant rules
        rules = rule_lookup.invoke(action_text)
        state.rule_check_result = f"Rules: {rules}"
        
        # 2. Roll dice (default action roll in Blades is 1d6)
        # In a full implementation, the number of dice would be determined by character skills
        roll_result = dice_roller.invoke("1d6")
        state.dice_roll_result = roll_result["total"]
        
        # 3. Determine outcome based on roll
        roll = roll_result["total"]
        if roll >= 6:
            outcome = "CRITICAL SUCCESS"
        elif roll >= 4:
            outcome = "PARTIAL SUCCESS"
        else:
            outcome = "FAILURE"
        
        state.rule_check_result = f"{outcome} (rolled {roll}). {rules}"
        
        return state
    
    return action_handler


def create_narrator(llm: BaseChatModel):
    """Create Narrator node for story generation."""
    
    def narrator(state: GameState) -> GameState:
        """Generate narrative response."""
        messages = state.messages
        dice_result = state.dice_roll_result
        rule_result = state.rule_check_result
        current_scene = state.current_scene
        current_hp = state.current_hp
        
        # Build context for narrator
        context = f"""
CURRENT SCENE: {current_scene or "The crew gathers in their dimly lit lair."}
PLAYER HP: {current_hp}
DICE RESULT: {dice_result}
RULE CHECK: {rule_result}
"""
        
        # Create prompt with system message and context
        prompt_messages = [
            SystemMessage(content=NARRATOR_SYSTEM_PROMPT),
            SystemMessage(content=f"GAME CONTEXT:\n{context}"),
            *messages
        ]
        
        response = llm.invoke(prompt_messages)
        
        # Add narrator response to messages
        state.messages = [*messages, AIMessage(content=response.content)]
        
        return state
    
    return narrator


def create_saver(session: Session):
    """Create Saver node to persist state."""
    
    def saver(state: GameState) -> GameState:
        """Save updated game state to database."""
        user_id = state.user_id
        
        if not user_id:
            return state
        
        # Find or create game state
        stmt = select(GameStateDB).where(GameStateDB.session_id == user_id)
        db_state = session.execute(stmt).scalar_one_or_none()
        
        if not db_state:
            db_state = GameStateDB(session_id=user_id)
            session.add(db_state)
        
        # Update fields
        db_state.current_scene = state.current_scene or db_state.current_scene
        if state.current_hp:
            if not db_state.player_stats:
                db_state.player_stats = {}
            db_state.player_stats["hp"] = state.current_hp
        
        session.commit()
        
        return state
    
    return saver


# =============================================================================
# Router Function
# =============================================================================

def route_by_intent(state: GameState) -> Literal["action_handler", "narrator"]:
    """Route based on player intent."""
    intent = state.rule_check_result
    
    if intent == "ACTION":
        return "action_handler"
    else:
        # DIALOGUE and QUERY go straight to narrator
        return "narrator"


# =============================================================================
# Graph Builder
# =============================================================================

def build_gm_agent(llm: BaseChatModel, session: Session) -> StateGraph:
    """
    Build the GM Agent graph.
    
    Graph flow:
        START -> state_loader -> intent_parser -> [router]
                                                    |
                                    ACTION: action_handler -> narrator -> saver -> END
                                    DIALOGUE/QUERY: narrator -> saver -> END
    """
    # Create nodes with dependencies
    state_loader = create_state_loader(session)
    intent_parser = create_intent_parser(llm)
    action_handler = create_action_handler(llm, session)
    narrator = create_narrator(llm)
    saver = create_saver(session)
    
    # Build graph
    graph = StateGraph(GameState)
    
    # Add nodes
    graph.add_node("state_loader", state_loader)
    graph.add_node("intent_parser", intent_parser)
    graph.add_node("action_handler", action_handler)
    graph.add_node("narrator", narrator)
    graph.add_node("saver", saver)
    
    # Add edges
    graph.set_entry_point("state_loader")
    graph.add_edge("state_loader", "intent_parser")
    graph.add_conditional_edges("intent_parser", route_by_intent)
    graph.add_edge("action_handler", "narrator")
    graph.add_edge("narrator", "saver")
    graph.add_edge("saver", END)
    
    return graph.compile()


# =============================================================================
# Usage Example
# =============================================================================

if __name__ == "__main__":
    # Example usage (requires LLM and database session)
    print("GM Agent module loaded successfully.")
    print("Use build_gm_agent(llm, session) to create the agent.")
