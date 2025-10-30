FROM --platform=linux/arm64 python:3.13

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Copy minimal requirements for private packages
COPY resources/requirements.txt /tmp/private-requirements.txt

# Configure pip to also use the public PyPI (causes no issues if unused)
RUN pip config set --site global.extra-index-url https://pypi.org/simple

# Install private dependencies (ds-threevictors) via internal index
ARG CA_URL
RUN --mount=type=secret,id=ca_token \
    pip install --no-cache-dir --index-url "https://aws:$(cat /run/secrets/ca_token)@${CA_URL#https://}" -r /tmp/private-requirements.txt

# Copy remaining project files
COPY . /app

# Install public dependencies and local packages
RUN python -m pip install --upgrade pip setuptools wheel \
 && python -m pip install --no-cache-dir openai-agents \
 && python -m pip install --no-cache-dir -r ds-mcp/requirements.txt \
 && python -m pip install --no-cache-dir -e ds-mcp -e ds_agents

ENTRYPOINT ["python", "chat.py"]
