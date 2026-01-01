"""
Global Pytest Configuration
===========================
Sets up environment variables for local testing to ensure connections
point to localhost instead of Docker internal hostnames.
"""

import os

# --- Aggressive Environment Patching ---
# We set these at the top level to ensure they take effect 
# before any other module imports or fixtures run.

print("DEBUG: Patching Envrionment Variables in conftest.py")

if "SQLALCHEMY_DATABASE_URL" not in os.environ:
    os.environ["SQLALCHEMY_DATABASE_URL"] = "postgresql+psycopg://postgres:postgres@localhost:5432/logos"

if "DATABASE_URL" not in os.environ:
    os.environ["DATABASE_URL"] = "postgresql://postgres:postgres@localhost:5432/logos"
    
if "LITELLM_URL" not in os.environ:
    os.environ["LITELLM_URL"] = "http://localhost:4000/v1"
    
if "OPENAI_API_BASE" not in os.environ:
    os.environ["OPENAI_API_BASE"] = "http://localhost:4000/v1"
    
if "OPENAI_API_KEY" not in os.environ:
    os.environ["OPENAI_API_KEY"] = "sk-litellm-master-key"

# ----------------------------------------

import pytest
