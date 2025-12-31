"""
Open WebUI Manifold Pipe - Logos Backend Bridge
================================================
This script exposes the Logos FastAPI agents as selectable "models" in Open WebUI.

Installation:
1. Go to Open WebUI Admin Panel -> Functions
2. Create a new Function (type: Pipe)
3. Paste this entire script
4. Configure the API_BASE_URL valve if needed

Compatible with Open WebUI 0.5.x+
"""

from typing import List, Union, Generator, Iterator, Optional
from pydantic import BaseModel, Field
import requests
import json


class Pipe:
    """
    Manifold Pipe that bridges Open WebUI to the Logos FastAPI backend.
    Each agent is registered as a separate "model" in the UI.
    """

    class Valves(BaseModel):
        """Configuration options exposed in Open WebUI settings."""
        API_BASE_URL: str = Field(
            default="http://host.docker.internal:8000",
            description="Base URL of the Logos FastAPI backend. Use host.docker.internal for Docker deployments."
        )
        REQUEST_TIMEOUT: int = Field(
            default=120,
            description="Request timeout in seconds for LLM responses."
        )

    def __init__(self):
        self.type = "manifold"
        self.id = "logos_agents"
        self.name = "Logos AI Agents"
        self.valves = self.Valves()

    def pipes(self) -> List[dict]:
        """
        Register available agents as selectable models in Open WebUI.
        Returns a list of agent definitions with id and display name.
        """
        return [
            # TRPG Agents
            {"id": "gm", "name": "🎲 TRPG Game Master"},
            {"id": "narrator", "name": "📖 TRPG Narrator"},
            {"id": "rulekeeper", "name": "⚖️ TRPG Rulekeeper"},
            
            # Research & Coding Agents
            {"id": "researcher", "name": "🔬 Deep Researcher"},
            {"id": "coder", "name": "💻 Code Assistant"},
            
            # Coaching Agents
            {"id": "coach", "name": "🏆 Life Coach"},
            {"id": "psychologist", "name": "🧠 Psychologist"},
            
            # Creative Writing Agents
            {"id": "writer", "name": "🖋️ Novelist"},
            {"id": "screenwriter", "name": "🎬 Screenwriter"},
        ]

    def pipe(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __event_emitter__=None,
        __event_call__=None,
    ) -> Union[str, Generator, Iterator]:
        """
        Main handler for incoming chat requests.
        
        Args:
            body: The request body from Open WebUI containing messages, model, etc.
            __user__: User information dict with 'id', 'email', 'name', 'role'
            __event_emitter__: Optional event emitter for status updates
            __event_call__: Optional event call handler
            
        Returns:
            Generator yielding response chunks (for streaming) or a string (for errors)
        """
        # Extract agent ID from model name (format: "logos_agents.gm")
        model_id = body.get("model", "")
        if "." in model_id:
            agent_id = model_id.split(".")[-1]
        else:
            agent_id = model_id
        
        # Map some aliases to actual backend endpoints
        agent_mapping = {
            "narrator": "gm",
            "rulekeeper": "gm",
            "psychologist": "coach",
            "coder": "researcher",
            "screenwriter": "writer",
        }
        backend_agent = agent_mapping.get(agent_id, agent_id)
        
        # Extract the last user message (we only send this, not full history)
        messages = body.get("messages", [])
        if not messages:
            return "Error: No messages provided."
        
        last_message = None
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_message = msg.get("content", "")
                break
        
        if not last_message:
            return "Error: No user message found."
        
        # Get session/conversation ID from Open WebUI
        # Open WebUI uses 'chat_id' in the body for conversation tracking
        session_id = body.get("chat_id", "default_session")
        
        # Get user info
        user_id = ""
        user_email = ""
        if __user__:
            user_id = __user__.get("id", "")
            user_email = __user__.get("email", "")
        
        # Build the minimal payload - let backend handle state from Postgres
        payload = {
            "query": last_message,  # User's strict requirement
            "session_id": session_id,
            "user_id": user_id or user_email or "anonymous",
        }
        
        # Construct the backend URL
        url = f"{self.valves.API_BASE_URL}/chat/{backend_agent}"
        
        # Emit status if available
        if __event_emitter__:
            __event_emitter__(
                {
                    "type": "status",
                    "data": {"description": f"Connecting to {backend_agent} agent...", "done": False},
                }
            )
        
        try:
            # Make request to FastAPI backend with streaming
            response = requests.post(
                url,
                json=payload,
                stream=True,
                timeout=self.valves.REQUEST_TIMEOUT,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code != 200:
                error_detail = response.text[:500] if response.text else "Unknown error"
                if __event_emitter__:
                    __event_emitter__(
                        {"type": "status", "data": {"description": f"Error: {response.status_code}", "done": True}}
                    )
                return f"❌ Backend Error ({response.status_code}): {error_detail}"
            
            # Check if response is streaming (SSE) or JSON
            content_type = response.headers.get("Content-Type", "")
            
            if "text/event-stream" in content_type:
                # Handle Server-Sent Events (SSE) streaming
                if __event_emitter__:
                    __event_emitter__(
                        {"type": "status", "data": {"description": "Streaming response...", "done": False}}
                    )
                
                def generate_sse():
                    for line in response.iter_lines():
                        if line:
                            line_str = line.decode("utf-8")
                            if line_str.startswith("data: "):
                                data = line_str[6:]
                                if data == "[DONE]":
                                    break
                                try:
                                    chunk = json.loads(data)
                                    if "content" in chunk:
                                        yield chunk["content"]
                                    elif "delta" in chunk and "content" in chunk["delta"]:
                                        yield chunk["delta"]["content"]
                                except json.JSONDecodeError:
                                    yield data
                    
                    if __event_emitter__:
                        __event_emitter__(
                            {"type": "status", "data": {"description": "Complete", "done": True}}
                        )
                
                return generate_sse()
            
            else:
                # Handle regular JSON response
                try:
                    result = response.json()
                    
                    if __event_emitter__:
                        __event_emitter__(
                            {"type": "status", "data": {"description": "Complete", "done": True}}
                        )
                    
                    # Extract the response content from various possible formats
                    if isinstance(result, str):
                        return result
                    elif "response" in result:
                        return result["response"]
                    elif "content" in result:
                        return result["content"]
                    elif "message" in result:
                        return result["message"]
                    elif "messages" in result and result["messages"]:
                        # Get the last assistant message
                        for msg in reversed(result["messages"]):
                            if msg.get("type") == "ai" or msg.get("role") == "assistant":
                                return msg.get("content", str(msg))
                        return str(result["messages"][-1])
                    else:
                        return json.dumps(result, ensure_ascii=False, indent=2)
                        
                except json.JSONDecodeError:
                    return response.text
        
        except requests.exceptions.ConnectionError:
            if __event_emitter__:
                __event_emitter__(
                    {"type": "status", "data": {"description": "Connection failed", "done": True}}
                )
            return (
                "❌ **Connection Error**\n\n"
                f"Cannot connect to the Logos backend at `{self.valves.API_BASE_URL}`.\n\n"
                "Please ensure:\n"
                "1. The FastAPI server is running (`uv run python src/main.py`)\n"
                "2. The API_BASE_URL valve is correctly configured\n"
                "3. If using Docker, use `host.docker.internal` instead of `localhost`"
            )
        
        except requests.exceptions.Timeout:
            if __event_emitter__:
                __event_emitter__(
                    {"type": "status", "data": {"description": "Request timed out", "done": True}}
                )
            return (
                "⏱️ **Request Timeout**\n\n"
                f"The request to `{backend_agent}` agent timed out after {self.valves.REQUEST_TIMEOUT} seconds.\n\n"
                "This may happen with complex queries. Try again or increase the timeout in valve settings."
            )
        
        except Exception as e:
            if __event_emitter__:
                __event_emitter__(
                    {"type": "status", "data": {"description": f"Error: {str(e)}", "done": True}}
                )
            return f"❌ **Unexpected Error**\n\n```\n{str(e)}\n```"
