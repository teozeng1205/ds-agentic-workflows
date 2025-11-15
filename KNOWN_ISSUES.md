# Issues & Improvement Opportunities

The sections below capture cross-repo problems observed while reviewing the current `agents` workspace. Each item includes file references plus concrete next steps so we can prioritize fixes.

## ds-agentic-workflows (root harness)

1. **Core tool filter hides the metadata utilities described in the prompts.**  
   `agent_core.EXPOSED_TOOLS` only allows `read_table_head`, `query_table`, `get_top_site_issues`, and `analyze_issue_scope` (ds-agentic-workflows/agent_core.py:21-33). The MCP server actually exposes six tools (ds-mcp/src/ds_mcp/server.py:90-234), but because the filter excludes `describe_table` and `get_table_schema`, the agent receives nondescript “tool not allowed” errors whenever it follows the documented workflow.  
   _Fix:_ Expand `EXPOSED_TOOLS` to include the metadata helpers (and any future table partitions tool) or disable the filter entirely when running trusted agents.

2. **Default table list references cross-database schemas that the metadata helpers cannot read.**  
   The shared `COMMON_TABLES` list advertises `prod.monitoring.provider_combined_audit` (agent_core.py:29-33), but `AnalyticsReader.describe_table/get_table_schema` only work when the requested table lives in the current Redshift database (ds-mcp/src/ds_mcp/core/connectors.py:86-147). Agents are instructed to “start with describe_table” (ds-agents/ds_agents/mcp_agents/generic.py:18-30), guaranteeing early failures on the default tables.  
   _Fix:_ either point `COMMON_TABLES` at same-database objects or add cross-database aware metadata functions so the recommended toolchain succeeds out of the box.

## ds-agents

1. **Prompts mention `get_table_partitions()` even though the tool does not exist.**  
   The instructions in `GenericDatabaseMCPAgent` still tell the model to call `get_table_partitions()` (ds-agents/ds_agents/mcp_agents/generic.py:18-23), but the MCP server never registers such a tool (ds-mcp/src/ds_mcp/server.py:90-234). Every attempt results in an MCP error that the agent tries to recover from.  
   _Fix:_ either implement and expose a real `get_table_partitions` helper in `ds-mcp` or edit the instructions to stop referencing it.

2. **Wrapper path assumes the monorepo structure and breaks when the package is installed elsewhere.**  
   `get_wrapper_script()` resolves `parents[3] / "ds-mcp" / "scripts" / "run_mcp_server.sh"` (ds-agents/ds_agents/mcp_agents/generic.py:34-35). When `ds_agents` is installed via pip into another project, that relative path no longer exists, so the MCP server can’t start.  
   _Fix:_ ship the launch script as part of the package (e.g., via `importlib.resources`), or make the wrapper path configurable through an environment variable/argument so the agent can run outside this repo.

## ds-mcp

1. **SQL parameters are interpolated directly, allowing injection.**  
   The connector builds SQL by embedding user-provided strings (table names, provider codes, dates) directly into the query (ds-mcp/src/ds_mcp/core/connectors.py:64-172 and 205-363). A crafted table name or provider code containing quotes can execute arbitrary SQL.  
   _Fix:_ sanitize identifiers and use parameterized queries (e.g., `cursor.execute(query, params)`) for every dynamic value, or at minimum validate the input using strict regex before interpolation.

2. **`run_mcp_server.sh --list` invokes an unsupported CLI flag.**  
   The launcher advertises `--list` (ds-mcp/scripts/run_mcp_server.sh:4-37) but the Python entry point doesn’t define such an argument (ds-mcp/src/ds_mcp/server.py:245-260). Running `run_mcp_server.sh --list` immediately raises `argparse` errors.  
   _Fix:_ either implement a real “list tables/slugs” mode in `ds_mcp.server` or remove the unreachable branch from the script.

3. **Slug-based table selection is not implemented.**  
   The script usage comment suggests `run_mcp_server.sh provider` (scripts/run_mcp_server.sh:5-8), yet the script merely appends `--table provider` and the server uses that literal string as a table name. There is no mapping between human-friendly slugs and actual schema.table names, so those invocations do nothing useful.  
   _Fix:_ add a lookup (e.g., load slug metadata from JSON) before building `--table` arguments, or update the documentation to make it clear that fully qualified table names are required.

## ds-chat backend

1. **Agent runner never recovers after a transient initialization failure.**  
   During startup the code sets `_agent_runner = None` if `AgentRunner.initialize()` raises (ds-chat/backend/app.py:68-133). All subsequent `/api/chat` requests simply return HTTP 503 because the handler never attempts to recreate the runner or lazily reinitialize it (ds-chat/backend/app.py:136-204).  
   _Fix:_ keep the `AgentRunner` instance even when initialization fails and retry `initialize()` on-demand (possibly with exponential backoff) instead of pinning the service in a broken state.

2. **Supplying a `session_id` creates orphan sessions and still fails to reuse the requested ID.**  
   The logic in `/api/chat` calls `_session_manager.create_session()` twice when the provided session does not exist (ds-chat/backend/app.py:162-172). `SessionManager.create_session()` always generates a fresh UUID (ds-chat/backend/session_manager.py:68-88), so the “Create new session with this ID” comment is wrong—one unused session leaks, and the caller still gets a brand new ID.  
   _Fix:_ reject unknown `session_id` values (HTTP 404) or add a `create_session(session_id=...)` path that actually honors the supplied identifier instead of minting throwaways.

3. **Session storage is per-process, unbounded, and not concurrency-safe.**  
   `SessionManager` keeps everything in an in-memory `dict` (backend/session_manager.py:48-167). There is no TTL, no pruning, and no locking, so running multiple Uvicorn workers produces divergent session stores and long-lived sessions accumulate indefinitely.  
   _Fix:_ move session state to a shared store (Redis/Postgres) or add expiration plus asyncio locks so multi-worker deployments behave deterministically.

4. **Path assumptions break deployments that don’t colocate `ds-chat` and `ds-agentic-workflows`.**  
   `AgentRunner` unconditionally prepends `../ds-agentic-workflows` to `sys.path` (backend/agent_runner.py:15-47). If the repos are not siblings, imports fail.  
   _Fix:_ make the agent root configurable via environment variable or require `agent_core`/`ds-mcp`/`ds-agents` to be installed as packages instead of relying on relative paths.

## ds-chat frontend

1. **Health checks ignore agent readiness.**  
   `healthCheck()` only inspects the HTTP status (frontend/lib/api.ts:35-43). If the backend returns `{"agent_initialized": false}`, the UI happily proceeds, calls `/api/chat`, and surfaces generic errors.  
   _Fix:_ parse the JSON payload and block initialization until `agent_initialized` is true; optionally poll until the agent is ready.

2. **“New chat” button is inert, so users cannot start a fresh session.**  
   The sidebar button lacks any `onClick` handler (frontend/components/Chat.tsx:82-104). The only way to reset the chat is to reload the page, which is confusing when experimenting with multiple conversations.  
   _Fix:_ wire the button to `SessionManager`—call `createSession()`, reset the Zustand store, and clear the history/log panels.

3. **Execution log panel shows fabricated data.**  
   `sendMessage()` generates hard-coded INFO entries with artificial delays (frontend/lib/api.ts:78-112) instead of streaming real events from the backend. The UI claims the agent performed certain steps even if the backend failed before running anything.  
   _Fix:_ remove the fake logs or replace them with actual telemetry (e.g., server-sent events, websocket stream, or metadata returned inside the `/api/chat` response).

4. **Initialization never clears error state when the backend comes back.**  
   `page.tsx` sets a fatal error message when `healthCheck()` fails once and never retries (frontend/app/page.tsx:12-35). If the backend starts later, the UI remains stuck until the page is refreshed.  
   _Fix:_ add a retry/backoff loop and clear prior errors when a subsequent health check passes.
