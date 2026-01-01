"""
Lobby Agent
===========
The reception area for the Logos AI OS.
Handles untargeted requests and routes users to the appropriate agent.
"""

from typing import Literal, Annotated, TypedDict, List
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage
from langchain_core.language_models import BaseChatModel
from langgraph.graph import StateGraph, END, MessageGraph
from langgraph.graph.message import add_messages

# --- State ---
class LobbyState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    next_agent: Literal["lobby", "gm", "writer", "coach", "researcher"]

# --- Prompts ---
LOBBY_SYSTEM_PROMPT = """You are the Central Hub Interface for Logos AI (Personal AI OS).
Your goal is to help the user select the valid module for their task.

Available Modules:
1. TRPG Game Master (gm): Runs Blades in the Dark / D&D games.
2. Novelist / Writer (writer): Assists with drafting novels or screenplays.
3. Life Coach / Psychologist (coach): Provides counseling, mood analysis, and advice.
4. Deep Researcher (researcher): Searches the web and summarizes papers.

Instructions:
- If the user's intent is clear, direct them to the module.
- If the user is just saying hello or asking what you can do, explain your capabilities briefly and ask what they want to do.
- Be polite, futuristic, and helpful.
- Do NOT try to perform the task yourself (e.g., don't start DMing a game). Route them.
"""

ROUTER_PROMPT = """Analyze the user's request and select the best agent.
Output ONLY one of the following words:
- gm (for games, roleplay, D&D)
- writer (for writing stories, scripts, editing)
- coach (for advice, therapy, venting)
- researcher (for search, coding, technical questions)
- lobby (if unclear, greeting, or capabilities question)

User Request: {input}
"""

def create_lobby_agent(llm: BaseChatModel):
    
    def router(state: LobbyState) -> LobbyState:
        # Check last message
        messages = state["messages"]
        last_msg = messages[-1].content
        
        response = llm.invoke([
            SystemMessage(content=ROUTER_PROMPT.format(input=last_msg)),
            HumanMessage(content="Select agent.")
        ])
        
        choice = response.content.strip().lower()
        # Fallback
        if choice not in ["gm", "writer", "coach", "researcher"]:
            choice = "lobby"
            
        return {"next_agent": choice}

    def responder(state: LobbyState) -> LobbyState:
        # Used only if next_agent is 'lobby'
        messages = state["messages"]
        response = llm.invoke([
            SystemMessage(content=LOBBY_SYSTEM_PROMPT),
            *messages
        ])
        return {"messages": [response]}

    # Graph
    graph = StateGraph(LobbyState)
    graph.add_node("router", router)
    graph.add_node("responder", responder)
    
    graph.set_entry_point("router")
    
    def route_logic(state: LobbyState):
        if state["next_agent"] == "lobby":
            return "responder"
        return END # In a real implementation, this might hand off to another graph
                   # But for API Gateway pattern, we usually return the routing decision 
                   # to the client or gateway to switch agents.
    
    graph.add_conditional_edges(
        "router",
        route_logic,
        {
            "responder": "responder",
            END: END
        }
    )
    
    graph.add_edge("responder", END)
    
    return graph.compile()
