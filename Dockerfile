FROM python:3.10-slim

WORKDIR /app

# Install system dependencies if required for sqlite-vec
RUN apt-get update && apt-get install -y build-essential curl && rm -rf /var/lib/apt/lists/*

# Install uv package manager
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

COPY pyproject.toml .
RUN uv sync

COPY . .

ENV WORKSPACE_ROOT="/workspace"
# Run daemon
ENTRYPOINT ["uv", "run", "visor-mcp"]
