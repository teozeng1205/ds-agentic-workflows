# syntax=docker/dockerfile:1.4
FROM --platform=linux/arm64 python:3.12

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

# Configure pip to also use the public PyPI (causes no issues if unused)
RUN pip config set --site global.extra-index-url https://pypi.org/simple

# Install private ds-threevictors when build secrets are provided
ARG CA_URL
RUN --mount=type=secret,id=ca_token \
    bash -lc 'if [ -n "${CA_URL:-}" ] && [ -f /run/secrets/ca_token ]; then \
        pip install --no-cache-dir --index-url "https://aws:$(cat /run/secrets/ca_token)@${CA_URL#https://}" ds-threevictors; \
      else \
        echo "Skipping ds-threevictors private install (set CA_URL and ca_token secret to enable)"; \
      fi'

# Install python dependencies (local editable installs)
RUN python -m pip install --upgrade pip setuptools wheel \
 && python -m pip install openai-agents \
 && python -m pip install -r /app/ds-mcp/requirements.txt \
 && python -m pip install -e /app/ds-mcp \
 && python -m pip install -e /app/ds-agents

# Default command: start provider chat (override with --agent anomalies)
CMD ["python", "chat.py", "--agent", "provider"]
