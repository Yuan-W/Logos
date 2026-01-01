"""
Check Embedding Dimension
"""
import os
from backend.utils.ingestion import get_embedding

try:
    vec = get_embedding("Helo World")
    print(f"Dimension: {len(vec)}")
except Exception as e:
    print(f"Error: {e}")
