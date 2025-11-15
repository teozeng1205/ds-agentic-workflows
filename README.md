# ds-agentic-workflows

Local development harness for the GenericDatabaseMCPAgent used by our analytics chat experiences.  
The repository bundles a CLI, the shared agent execution engine, and the MCP server + agent packages so you can test conversational workflows end-to-end without extra glue code.

## Contents

- `chat.py` – interactive CLI that speaks to the GenericDatabaseMCPAgent.
- `agent_core.py` – shared async executor used by both the CLI and the ds-chat FastAPI backend.
- `ds-agents/` – Python package with provider/anomalies agent definitions and wrappers.
- `ds-mcp/` – Model Context Protocol (MCP) server exposing Redshift analytics tables as tools.
- `env.sh` – template for AWS/OpenAI environment variables (source before running anything).

## Requirements

- Python 3.10+ (3.12 recommended)
- Access to the ATPCO Redshift reader via VPN + AWS SSO (e.g., `3VDEV` profile)
- OpenAI API key for `openai-agents`
- `ds-threevictors` package (internal) for AnalyticsReader connectivity

## Setup

```bash
git clone --recurse-submodules <repo>
cd ds-agentic-workflows

python3 -m venv .venv
source .venv/bin/activate

pip install -U openai-agents
pip install -r ds-mcp/requirements.txt
pip install -e ds-threevictors  # from your internal index

cp env.sh env.local && source env.local   # ensure AWS_* and OPENAI_API_KEY are set
```

Running from the repo root automatically injects `ds-agents/` and `ds-mcp/src/` into `PYTHONPATH`, so editable installs are optional.

## Usage

### CLI

```bash
python chat.py              # Generic database agent
# Once running:
#  • Type questions about prod.monitoring or local.analytics tables
#  • Use /exit to quit
```

Pass `--allow-query-table` to enable ad-hoc SQL or set `COMMON_TABLES`/`EXPOSED_TOOLS` in `agent_core.py` to tailor access.

### Web Backends

`agent_core.AgentExecutor` is the shared engine used by the ds-chat FastAPI backend. Import it to embed the same conversational agent into other applications without reimplementing MCP lifecycle handling.

## Docker

```bash
docker compose build
OPENAI_API_KEY=sk-... docker compose run --rm chat                  # Provider defaults
OPENAI_API_KEY=sk-... CHAT_AGENT=anomalies docker compose run --rm chat
```

The container mounts `env.sh` and `~/.aws` so the MCP subprocess inherits the correct credentials.

## Troubleshooting

- **Timeouts initializing MCP server** – verify VPN + AWS SSO session (`aws sso login --profile 3VDEV`).
- **Missing dependencies** – ensure `pip install -r ds-mcp/requirements.txt` and `pip install -U openai-agents` succeeded inside your virtual environment.
- **Import errors** – run commands from the repo root so the relative `sys.path` adjustments in `agent_core.py` take effect.
