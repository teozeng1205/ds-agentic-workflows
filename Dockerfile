FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Install system deps and AWS CLI v2
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    unzip \
    bash \
 && rm -rf /var/lib/apt/lists/*

# Install AWS CLI v2 (used by MCP wrappers for SSO), architecture-aware
RUN ARCH=$(uname -m) \
 && if [ "$ARCH" = "x86_64" ] || [ "$ARCH" = "amd64" ]; then CLI_URL="https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip"; \
    elif [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then CLI_URL="https://awscli.amazonaws.com/awscli-exe-linux-aarch64.zip"; \
    else CLI_URL="https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip"; fi \
 && curl -sSL "$CLI_URL" -o "/tmp/awscliv2.zip" \
 && unzip -q /tmp/awscliv2.zip -d /tmp \
 && /tmp/aws/install \
 && rm -rf /tmp/aws /tmp/awscliv2.zip

WORKDIR /app

# Copy repository
COPY . /app

# Install python dependencies (local editable installs)
RUN python -m pip install --upgrade pip setuptools wheel \
 && python -m pip install openai-agents \
 && python -m pip install -e /app/ds-threevictors \
 && python -m pip install -r /app/ds-mcp/requirements.txt \
 && python -m pip install -e /app/ds-mcp

# Default command: start provider chat (override with --agent anomalies)
CMD ["python", "ds-agents/chat.py", "--agent", "provider"]
