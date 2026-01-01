"""
Logos AI OS - Unified Entrypoint
================================
Thin wrapper to run the FastAPI Gateway.
"""

from backend.gateway.api import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
