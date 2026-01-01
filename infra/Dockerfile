FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency files
COPY pyproject.toml uv.lock README.md ./

# Install dependencies using uv
RUN uv sync --frozen --no-install-project

# Copy application source
COPY backend/ /app/backend/
COPY main.py /app/
COPY alembic.ini /app/
COPY alembic/ /app/alembic/

# Copy Frontend (Optional now if simplified, but keeping for reference)
# COPY frontend/ /app/frontend/

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8000

# Start command
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
