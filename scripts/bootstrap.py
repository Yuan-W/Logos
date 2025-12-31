"""
Bootstrap Script
================
One-stop initialization for the Logos project.
Usage: python scripts/bootstrap.py

Performs:
1. Environment Check (UV, Docker)
2. Dependency Sync (uv sync)
3. Database Setup (Docker Compose up)
4. Database Migration (Alembic upgrade head)
"""

import os
import subprocess
import time
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
OS_ENV = os.environ.copy()

def run_cmd(cmd: str, cwd=None, check=True):
    print(f"Running: {cmd}")
    subprocess.run(cmd, shell=True, check=check, cwd=cwd or PROJECT_ROOT, env=OS_ENV)

def check_requirements():
    print("Checking dependencies...")
    # Check uv
    try:
        run_cmd("uv --version", check=False)
    except Exception:
        print("Error: 'uv' not found. Please install uv.")
        sys.exit(1)
        
    # Check docker
    try:
        run_cmd("docker --version", check=False)
    except Exception:
        print("Warning: 'docker' not found. Ensure Postgres is running manually if not using Docker.")

def bootstrap():
    print("=== Logos Bootstrap ===\n")
    
    check_requirements()
    
    # 1. Sync Dependencies
    print("\n[Step 1] Syncing Python Dependencies...")
    run_cmd("uv sync")
    
    # 2. Start Database
    print("\n[Step 2] Starting Database Infrastructure...")
    docker_compose_file = PROJECT_ROOT / "infra" / "docker-compose.yml"
    if docker_compose_file.exists():
        run_cmd(f"docker-compose -f {docker_compose_file} up -d")
        print("Waiting for Database to accept connections...")
        time.sleep(5) # Simple wait, better would be a connection loop check
    else:
        print("No docker-compose.yml found in infra/, skipping container start.")

    # 3. Run Migrations
    print("\n[Step 3] Running Database Migrations...")
    # Ensure alembic uses the project root
    run_cmd("uv run alembic upgrade head")
    
    print("\n=== Bootstrap Complete! ===")
    print("You can now run the server with: uv run python src/main.py")

if __name__ == "__main__":
    bootstrap()
