# Use an official Python runtime as a parent image
FROM python:3.13-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

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
ENV MCP_TRANSPORT=sse
ENV PORT=45666
ENV DATABASE_PATH=/app/data/smart_task.db

# Use the virtual environment created by uv
CMD ["/app/.venv/bin/python", "main.py"]
