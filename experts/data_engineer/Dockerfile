FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1
ENV UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
# Copy project files
COPY pyproject.toml .
# Install dependencies
RUN uv sync --no-dev --no-install-project

# Copy the rest of the application
COPY . .

# Expose A2A Port
EXPOSE 9013

# Start the ADK API Server
CMD ["uv", "run", "adk", "api_server", "./", "--port", "9013", "--host", "0.0.0.0"]
