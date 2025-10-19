# ds-agentic-workflows

Minimal steps to run the interactive chat client that talks to the MCP servers (Provider Combined Audit or Market Anomalies).

Quick start
- Ensure submodules are present: `git submodule update --init --recursive`
- Create venv and activate: `python3 -m venv .venv && source .venv/bin/activate`
- Install base agents lib: `pip install -U openai-agents`
- Install ds-agents package (local): `pip install -e ds-agents`
- Install MCP deps (local): `pip install -r ds-mcp/requirements.txt && pip install -e ds-mcp`
- Create `env.sh` at repo root with at least: `AWS_PROFILE`, `AWS_DEFAULT_REGION`, `OPENAI_API_KEY` (see `ds-mcp/README.md`)
- Run chat
  - Provider: `python chat.py --agent provider`
  - Anomalies: `python chat.py --agent anomalies`

Notes
- `chat.py` is at the repo root and loads agent definitions from `ds-agents/agents/`.
- Python import names use underscores: `from ds_agents import ...` and `from ds_mcp import ...`.
- The chat client launches the installed `ds_mcp` server modules directly (no repo paths).
