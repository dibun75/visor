FROM python:3.10-slim

WORKDIR /app

# Multi-stage copy to inject the `uv` binaries instantly securely
COPY --from=ghcr.io/astral-sh/uv /uv /uvx /bin/

# Install system dependencies
RUN apt-get update && apt-get install -y build-essential curl sqlite3 && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN uv sync

COPY . .

ENV WORKSPACE_ROOT="/workspace"
ENTRYPOINT ["uv", "run", "visor-mcp"]
