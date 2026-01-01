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

from typing import Annotated, Literal, Optional, Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from langgraph.graph.message import add_messages
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from backend.graph.state import GameState
from backend.database.models import GameState as GameStateDB
from backend.database.db_init import get_session
from backend.agents.tools import dice_roller, create_rule_lookup, update_character, lookup_stats
from backend.agents.common.summarizer import create_summarizer
from backend.agents.nodes.editor import create_editor


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

PREVIOUS SUMMARY:
{conversation_summary}

{glossary_context}

IMPORTANT: You MUST generate the narrative in CHINESE (Simplified Chinese).
保持中文回复。使用中文描述场景、动作和后果。但是游戏术语（如 "Blades in the Dark", "Action Roll"）可以保留英文或说明。"""

INTENT_PARSER_PROMPT = """Analyze the player's message and determine if it requires:
1. ACTION - Requires dice roll and/or rule check (combat, stealth, persuasion, etc.)
2. DIALOGUE - Roleplay conversation with NPCs or the world
3. QUERY - Player asking about game state, rules, or situation

Respond with ONLY one word: ACTION, DIALOGUE, or QUERY

Player message: {message}"""


STORYTELLER_SYSTEM_PROMPT = """你是一位叙事者 (Storyteller)，负责用优雅的中文描述 TRPG 游戏中的场景和结果。

风格指南:
- 使用生动、电影化的描写
- 强调氛围：光影、声音、紧张感
- 对话用角色的语气和口吻
- 结果应戏剧化，但不夸张

你的任务是根据以下信息生成一段叙事：
- 玩家行动: {player_action}
- 骰子结果: {dice_result}
- 规则检定: {rule_check}
- 当前场景: {current_scene}

{revision_feedback}

请直接输出叙事内容，不要添加元数据或解释。"""


RULES_LAWYER_PROMPT = """你是一位冷酷的规则专家 (Rules Lawyer)。你的唯一任务是检查叙事者的描述是否符合游戏规则。

你必须检查:
1. **行动经济**: 角色是否在一回合内采取了过多行动？
2. **数值正确性**: HP、伤害、AC 等数值是否与规则书一致？
3. **资源消耗**: 法术位、弹药等资源是否足够？
4. **规则合规**: 动作描述是否符合游戏机制？

规则参考:
{rules_context}

角色状态:
{character_status}

叙事者的草稿:
---
{draft_narrative}
---

你的输出必须是以下两种之一:
- `APPROVED` - 如果叙事完全符合规则
- `OBJECTION: [具体问题]` - 如果发现规则违规，明确指出问题

只输出一行判决，不要添加任何解释。"""

PERSONA_CHAT_PROMPT = """You are the Dungeon Master (The Arbiter).
You are NOT narrating the story right now. You are talking TO the player about the game, rules, or your role.

Persona:
- Authoritative but fair.
- Use TTRPG terminology (Checks, Mechanics, Agency).
- If asked about your identity, describe yourself as the interface between the player's choices and the world's consequences.
- Do NOT advance the plot. Answer the question directly.

User Query: {query}
"""

INTENT_ROUTER_PROMPT = """Classify the user's message.
TYPE A: ACTION (The player wants to DO something in the game: "Attack", "Look around", "I cast fireball")
TYPE B: INTERACTION (Meta-discussion: "Who are you?", "How does this rule work?", "Change the setting")

Output ONLY: ACTION or INTERACTION.

Message: {message}"""

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


@tool
def lookup_stats(query: str):
    """
    Look up precise numerical stats (HP, AC, CR) for monsters/spells from the Rulebook.
    Use this when the user asks for specific stats or you need to run combat mechanics.
    """
    session = get_session()
    try:
        # JSONB Path query to find matching name in stat_blocks
        # Assuming structure: {"items": [{"name": "Goblin", ...}]}
        # We use a broad LIKE search on the JSON as text or specific key if known.
        # Simple implementation: vector search RuleBookChunk + filter by json content
        # Better: SQL JSON path search.
        
        # Postgres JSONB containment: @>
        # Let's try finding chunk containing the name.
        
        sql = text("""
            SELECT stat_block FROM rulebook_chunks 
            WHERE content ILIKE :q 
            LIMIT 1
        """)
        result = session.execute(sql, {"q": f"%{query}%"}).scalar()
        
        if result:
            return str(result)
        return "No stats found."
    finally:
        session.close()


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
        
        # 1. Try to look up precise stats first (for combat, spell damage)
        stats = lookup_stats.invoke(action_text)
        
        # 2. If no stats found, look up lore/rules text
        if "No stats found" in stats:
            rules = rule_lookup.invoke(action_text)
        else:
            rules = f"[Stats Found]: {stats}"
        
        state.rule_check_result = f"Rules: {rules}"
        
        # 3. Roll dice (default action roll in Blades is 1d6)
        roll_result = dice_roller.invoke("1d6")
        state.dice_roll_result = roll_result["total"]
        
        # 4. Determine outcome based on roll
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


def create_storyteller(llm: BaseChatModel):
    """Create Storyteller node for narrative generation."""
    
    def storyteller(state: GameState) -> GameState:
        """Generate cinematic narrative draft."""
        messages = state.messages
        
        if not messages:
            return state
        
        last_message = messages[-1]
        player_action = last_message.content if isinstance(last_message, HumanMessage) else ""
        
        # Build revision feedback if this is a retry
        revision_feedback = ""
        if state.lawyer_feedback and "OBJECTION" in state.lawyer_feedback:
            revision_feedback = f"\n\n【修正要求】规则专家指出问题:\n{state.lawyer_feedback}\n请修正你的叙事以符合规则。"
        
        prompt = STORYTELLER_SYSTEM_PROMPT.format(
            player_action=player_action,
            dice_result=state.dice_roll_result,
            rule_check=state.rule_check_result,
            current_scene=state.current_scene or "场景尚未设定",
            revision_feedback=revision_feedback
        )
        
        response = llm.invoke([
            SystemMessage(content=prompt),
            HumanMessage(content="请生成叙事描述。")
        ])
        
        state.draft_narrative = response.content
        state.adversarial_iteration += 1
        
        return state
    
    return storyteller


def create_rules_lawyer(llm: BaseChatModel, session: Session):
    """Create Rules Lawyer node for validation."""
    from backend.tools.character_manager import get_character_prompt_block
    
    def rules_lawyer(state: GameState) -> GameState:
        """Validate narrative against rules and character state."""
        draft = state.draft_narrative
        
        if not draft:
            state.lawyer_feedback = "APPROVED"
            return state
        
        # Get rules context
        rules_context = state.rule_check_result
        
        # Get character status if available
        character_status = "角色状态不可用"
        if state.active_character_id:
            try:
                character_status = get_character_prompt_block(state.active_character_id, session)
            except Exception:
                pass
        
        prompt = RULES_LAWYER_PROMPT.format(
            rules_context=rules_context,
            character_status=character_status,
            draft_narrative=draft
        )
        
        response = llm.invoke([
            SystemMessage(content=prompt),
            HumanMessage(content="请判定。")
        ])
        
        verdict = response.content.strip()
        state.lawyer_feedback = verdict
        
        return state
    
    return rules_lawyer


def route_by_verdict(state: GameState) -> str:
    """Route based on Rules Lawyer verdict."""
    feedback = state.lawyer_feedback
    iteration = state.adversarial_iteration
    
    # Max 3 iterations, then force output
    if iteration >= 3:
        return "finalize"
    
    if feedback.startswith("APPROVED"):
        return "finalize"
    else:
        # OBJECTION - loop back to storyteller
        return "storyteller"



def create_narrator(llm: BaseChatModel, glossary_context: str = ""):
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
            SystemMessage(content=NARRATOR_SYSTEM_PROMPT.format(
                conversation_summary=state.conversation_summary,
                glossary_context=glossary_context
            )),
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

def create_intent_classifier(llm: BaseChatModel):
    """Classify user message as ACTION or INTERACTION."""
    
    def classifier(state: GameState) -> GameState:
        messages = state.messages
        if not messages:
            state.rule_check_result = "INTERACTION"
            return state
            
        last_msg = messages[-1]
        content = last_msg.content if isinstance(last_msg, HumanMessage) else ""
        
        response = llm.invoke([
            SystemMessage(content=INTENT_ROUTER_PROMPT.format(message=content))
        ])
        
        classification = response.content.strip().upper()
        # Overload rule_check_result temporarily for routing (hacky but efficient for now)
        # Better practice: Add 'intent' field to GameState. 
        # Since I can't edit schema easily here without migration, I'll use metadata or existing field?
        # GameState has no 'intent' field. I'll rely on a temporary attribute or context.
        # Actually I can just return it in a dict update if using functional API, but we are using State object.
        # Let's use `rule_check_result` as the "Temp Slot" since it is reset every turn.
        state.rule_check_result = classification
        return state
        
    return classifier

def create_persona_chat(llm: BaseChatModel):
    """Handle meta-interactions."""
    
    def persona_chat(state: GameState) -> GameState:
        messages = state.messages
        last_msg = messages[-1].content if messages else ""
        
        response = llm.invoke([
            SystemMessage(content=PERSONA_CHAT_PROMPT.format(query=last_msg))
        ])
        
        state.messages = [*messages, AIMessage(content=response.content)]
        return state
        
    return persona_chat

def route_root(state: GameState) -> str:
    """Route from Classifier."""
    # Using rule_check_result as the intent carrier
    intent = state.rule_check_result
    if intent == "ACTION":
        return "work"
    return "chat"

# =============================================================================
# Router Function (Deprecated / Internal)
# =============================================================================

def route_work_logic(state: GameState) -> Literal["handler", "narrator"]:
    """Old IntentParser logic, now strictly for Work Graph."""
    # This was the old "ACTION/DIALOGUE/QUERY" split.
    # Now we assume if we are in Work Graph, it is In-Game.
    # We might still want to parse if it calls for dice (ACTION) or just talking (DIALOGUE/QUERY).
    # Re-using intent_parser node logic?
    # For now let's just use the existing intent_parser node inside the Work branch.
    intent = state.rule_check_result # Note: this will be overwritten by intent_parser node!
    
    if intent == "ACTION":
        return "handler"
    else:
        return "narrator"


# =============================================================================
# Graph Builder
# =============================================================================

def build_gm_agent(llm: BaseChatModel, session: Session, checkpointer: Optional[Any] = None, glossary_context: str = "") -> CompiledStateGraph:
    """
    Build the GM Agent graph with Adversarial Loop (Storyteller + Rules Lawyer).
    
    Graph flow:
        START -> state_loader -> intent_parser -> [router]
                                                    |
                    ACTION: handler -> storyteller -> rules_lawyer -> [verdict]
                                                                         |
                                          APPROVED: finalize -> editor -> saver -> summarizer -> END
                                          OBJECTION: storyteller (retry, max 3x)
                    
                    DIALOGUE/QUERY: storyteller -> rules_lawyer -> ... (same loop)
    """
    # Create nodes with dependencies
    classifier = create_intent_classifier(llm)
    persona_chat = create_persona_chat(llm)
    
    state_loader = create_state_loader(session)
    intent_parser = create_intent_parser(llm)
    action_handler = create_action_handler(llm, session)
    storyteller = create_storyteller(llm)
    rules_lawyer = create_rules_lawyer(llm, session)
    saver = create_saver(session)
    summarizer = create_summarizer(llm)
    editor = create_editor(llm, session)
    
    # Finalize node: transfers draft to messages
    def finalize(state: GameState) -> GameState:
        """Finalize narrative: move draft to messages."""
        if state.draft_narrative:
            state.messages = [*state.messages, AIMessage(content=state.draft_narrative)]
        # Reset adversarial state
        state.draft_narrative = ""
        state.lawyer_feedback = ""
        state.adversarial_iteration = 0
        return state
    
    # Build graph
    graph = StateGraph(GameState)
    
    # Add nodes
    graph.add_node("classifier", classifier)
    graph.add_node("persona_chat", persona_chat)
    
    graph.add_node("state_loader", state_loader)
    graph.add_node("intent_parser", intent_parser)
    graph.add_node("handler", action_handler)
    graph.add_node("storyteller", storyteller)
    graph.add_node("rules_lawyer", rules_lawyer)
    graph.add_node("finalize", finalize)
    graph.add_node("editor", editor)
    graph.add_node("saver", saver)
    graph.add_node("summarizer", summarizer)
    
    # Add edges
    # START -> classifier
    graph.set_entry_point("classifier")
    
    # Classifier -> Conditional
    graph.add_conditional_edges("classifier", route_root, {
        "work": "state_loader",
        "chat": "persona_chat"
    })
    
    # Branch 1: Chat
    graph.add_edge("persona_chat", END)
    
    # Branch 2: Work (Game Loop)
    graph.add_edge("state_loader", "intent_parser")
    
    # Intent router (Inside Work Graph)
    graph.add_conditional_edges("intent_parser", route_work_logic, {
        "handler": "handler",
        "narrator": "storyteller"
    })
    
    # Action handler -> Storyteller
    graph.add_edge("handler", "storyteller")
    
    # Storyteller -> Rules Lawyer
    graph.add_edge("storyteller", "rules_lawyer")
    
    # Rules Lawyer -> Conditional (Approved or Objection)
    graph.add_conditional_edges("rules_lawyer", route_by_verdict, {
        "finalize": "finalize",
        "storyteller": "storyteller"
    })
    
    # Finalize -> Editor -> Saver -> Summarizer -> END
    graph.add_edge("finalize", "editor")
    graph.add_edge("editor", "saver")
    graph.add_edge("saver", "summarizer")
    graph.add_edge("summarizer", END)
    
    return graph.compile(checkpointer=checkpointer)


# =============================================================================
# Usage Example
# =============================================================================

if __name__ == "__main__":
    # Example usage (requires LLM and database session)
    print("GM Agent module loaded successfully.")
    print("Use build_gm_agent(llm, session) to create the agent.")
