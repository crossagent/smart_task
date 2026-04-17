# Use an official Python runtime as a parent image
FROM python:3.13-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install system dependencies (Git, SSH, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    openssh-client \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Basic Git Configuration
RUN git config --global user.name "Smart Task Agent" && \
    git config --global user.email "agent@smart-task.hub" && \
    git config --global pull.rebase true && \
    git config --global rebase.autoStash true

# Set the working directory in the container
WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy project files
COPY pyproject.toml uv.lock ./

# Install dependencies (caching the cache)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project

# Copy the rest of the application code
COPY . .

# Install the project
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen

# Expose the port for SSE transport
EXPOSE 45666

# Set default environment variables for Docker deployment
ENV MCP_TRANSPORT=http
ENV PORT=45666

# Use the virtual environment created by uv
CMD ["/app/.venv/bin/python", "-m", "src.mcp_server.server"]
