"""
Test Client
===========
Simulates Open WebUI requests to the Logos API Gateway.
"""

import requests
import json
import uuid

BASE_URL = "http://localhost:8000"

def test_agent(role: str, message: str, **kwargs):
    print(f"\n--- Testing Agent: {role.upper()} ---")
    print(f"Input: {message}")
    
    payload = {
        "user_id": f"test_user_{uuid.uuid4().hex[:8]}",
        "message": message,
        **kwargs
    }
    
    try:
        response = requests.post(f"{BASE_URL}/chat/{role}", json=payload)
        response.raise_for_status()
        
        data = response.json()
        print(f"Response: {data['response']}")
        print(f"State Summary: {json.dumps(data['final_state'], indent=2)}")
        return True
    except Exception as e:
        print(f"Error: {e}")
        if hasattr(e, 'response') and e.response:
            print(e.response.text)
        return False

def run_tests():
    # 1. GM Agent
    test_agent("gm", "I kick open the door and attack the goblin!")
    
    # 2. Researcher Agent
    test_agent("researcher", "What are the key themes in the uploaded papers?")
    
    # 3. Coach Agent (Psychologist)
    test_agent("coach", "I'm feeling really stressed about deadlines.", role_mode="psychologist")
    
    # 4. Writer Agent (Novelist)
    test_agent("writer", "A rainy cyberpunk street scene.", project_id="cyber_01")

if __name__ == "__main__":
    # Ensure server is running first!
    print("Ensure src/main.py is running on port 8000.")
    run_tests()
