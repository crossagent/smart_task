# Use a slim Python 3.13 image as base
FROM python:3.13-slim

# Switch to Tsinghua mirror for faster builds in China
RUN sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources

# Install system dependencies (Git is required for our bootstrap strategy)
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv (standard for all our agents)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Set up the application directory
WORKDIR /app

# Copy the bootstrap script OUTSIDE of /app to prevent self-deletion during bootstrap
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Entrypoint is the orchestrator of expert isolation
ENTRYPOINT ["/entrypoint.sh"]

# Default command (can be overridden in docker-compose)
CMD ["python"]
