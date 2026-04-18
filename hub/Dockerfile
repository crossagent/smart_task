# Project Manager (hub_pm) Agent Machine
FROM python:3.11-slim-bookworm

# Install core tools for Git communication
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv (standard for all our agents)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Set up the application directory
WORKDIR /app

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/app
ENV PATH="/app/.venv/bin:$PATH"

# Default command: Start the Agent using uv run for automatic dependency sync
CMD ["uv", "run", "adk", "api_server", "./", "--port", "9010"]
