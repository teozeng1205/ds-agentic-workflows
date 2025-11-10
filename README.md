# ds-agentic-workflows

Minimal steps to run the interactive chat client that talks to the MCP servers (Provider Combined Audit or Market Anomalies).

Quick start
- Ensure submodules are present: `git submodule update --init --recursive`
- Create venv and activate: `python3 -m venv .venv && source .venv/bin/activate`
- Install base agents lib: `pip install -U openai-agents`
- Install shared dependencies: `pip install -r ds-mcp/requirements.txt`
- Install the internal ds-threevictors package (required for database access): `pip install -e ds-threevictors` or use your internal package index.
- Create `env.sh` at repo root with at least: `AWS_PROFILE`, `AWS_DEFAULT_REGION`, `OPENAI_API_KEY` (see `ds-mcp/README.md`)
- Run chat
  - Provider defaults: `python chat.py --agent provider`
  - Anomalies defaults: `python chat.py --agent anomalies`
  - Generic agent prompts you to select which tables/slugs to enable (or choose ALL) before the session starts
  - Allow manual SQL via `--allow-query-table` (disabled by default)

### Web UI (ChatKit)

See `../ds-chat/README.md` for a lightweight ChatKit-based web interface that
lets you pick tables from the browser and talk to the generic agent using
OpenAI's ChatKit embeds.

Docker
- Build once: `docker compose build`
- Provider chat: `OPENAI_API_KEY=sk-... docker compose run --rm chat`
- Other agent: `OPENAI_API_KEY=sk-... CHAT_AGENT=anomalies docker compose run --rm chat`

Notes
- `chat.py` is at the repo root and loads agent definitions from `ds-agents/agents/`.
- Python import names use underscores: `from ds_agents import ...` and `from ds_mcp import ...`.
- Running `chat.py` from the repo root automatically adds the local `ds-agents` and `ds-mcp/src` paths to `sys.path`, so editable installs (`pip install -e`) are optional.
- The chat client launches the installed `ds_mcp` server modules directly (no repo paths).
