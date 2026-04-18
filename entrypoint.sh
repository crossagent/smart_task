#!/bin/bash
set -e

# Configure Git to use the Auth Token for all GitHub operations if provided
if [ -n "$GIT_AUTH_TOKEN" ]; then
    git config --global url."https://${GIT_AUTH_TOKEN}@github.com/".insteadOf "https://github.com/"
    echo "Git authentication configured for github.com"
fi

# Expert Repository Bootstrap logic
if [ -n "$GIT_REMOTE_URL" ] && [ ! -d ".git" ]; then
    echo "Expert Isolation: Bootstrapping specialized repository from $GIT_REMOTE_URL..."
    
    # We don't save the old .venv anymore because each expert manages its own dependencies
    # and we want to ensure 100% correct dependency resolution for the specific agent.
    # To speed up, we keep the /app folder empty except for what git brings.
    
    # Wipe the /app directory contents (including hidden files)
    find /app -mindepth 1 -delete
    
    # Clone the repository directly into /app
    git clone --recursive "$GIT_REMOTE_URL" /app
    
    echo "Expert repository successfully cloned."
    
    # AUTONOMOUS DEPENDENCY SYNC
    # This creates a local .venv tailored to the agent's specific pyproject.toml
    echo "Expert Isolation: Synchronizing dependencies via uv sync..."
    # Disable exit-on-error temporarily to allow fallback from --frozen if lockfile is missing
    set +e
    uv sync --frozen
    if [ $? -ne 0 ]; then
        echo "No lockfile or frozen sync failed. Performing fresh uv sync..."
        uv sync
    fi
    set -e
    echo "Expert dependencies successfully synchronized."
fi

# Ensure PYTHONPATH includes /app
export PYTHONPATH=$PYTHONPATH:/app

# If a local .venv exists (created by uv sync), use its executables
if [ -d "/app/.venv/bin" ]; then
    export PATH="/app/.venv/bin:$PATH"
    echo "Using autonomous virtual environment at /app/.venv"
fi

exec "$@"
