"""
Shared core logic for agent execution.

This module contains the common agent execution logic used by both:
- chat.py (CLI interface)
- ds-chat/backend/agent_runner.py (Web API backend)

Extracts shared functionality to avoid code duplication and ensure
both implementations stay in sync.
"""

from __future__ import annotations

import os
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

# Core tools exposed to the agent
EXPOSED_TOOLS = [
    "read_table_head",
    "query_table",
    "get_top_site_issues",
    "analyze_issue_scope",
]

# Common tables to expose to the agent (configurable)
COMMON_TABLES = [
    "prod.monitoring.provider_combined_audit",
    "local.analytics.market_level_anomalies_v3",
]


class AgentExecutorError(Exception):
    """Base exception for agent executor errors."""
    pass


def setup_import_paths(repo_root: Path | None = None) -> list[str]:
    """
    Setup sys.path to import local submodules without pip installs.

    Args:
        repo_root: Root directory containing ds-agents and ds-mcp.
                  If None, assumes current file is in ds-agentic-workflows.

    Returns:
        List of path strings that were added to sys.path
    """
    if repo_root is None:
        repo_root = Path(__file__).resolve().parent

    local_import_paths = [
        repo_root / "ds-agents",
        repo_root / "ds-mcp" / "src",
    ]

    added_paths = []
    for path in local_import_paths:
        if path.exists():
            str_path = str(path)
            added_paths.append(str_path)
            if str_path not in sys.path:
                sys.path.insert(0, str_path)

    return added_paths


class AgentExecutor:
    """
    Core agent execution logic shared between CLI and web implementations.

    Handles:
    - MCP server lifecycle management
    - Agent instance creation and configuration
    - Turn execution with metrics tracking
    - Resource cleanup
    """

    def __init__(
        self,
        common_tables: list[str] | None = None,
        exposed_tools: list[str] | None = None,
        repo_root: Path | None = None,
    ):
        """
        Initialize the agent executor.

        Args:
            common_tables: List of tables to expose to the agent.
                          Defaults to COMMON_TABLES if None.
            exposed_tools: List of tools to expose to the agent.
                          Defaults to EXPOSED_TOOLS if None.
            repo_root: Root directory containing ds-agents and ds-mcp.
                      If None, assumes current file is in ds-agentic-workflows.
        """
        self.common_tables = common_tables or COMMON_TABLES
        self.exposed_tools = exposed_tools or EXPOSED_TOOLS
        self.repo_root = repo_root or Path(__file__).resolve().parent

        # Setup import paths
        self.local_import_path_strs = setup_import_paths(self.repo_root)

        # Lazy imports after path setup
        from agents import Runner
        from agents.mcp import MCPServerStdio, create_static_tool_filter
        from ds_agents.mcp_agents import GenericDatabaseMCPAgent

        self.Runner = Runner
        self.MCPServerStdio = MCPServerStdio
        self.create_static_tool_filter = create_static_tool_filter
        self.GenericDatabaseMCPAgent = GenericDatabaseMCPAgent

        # State
        self.mcp_server = None
        self.agent_instance = None
        self._last_result = None

    async def initialize(self) -> None:
        """
        Initialize the MCP server and agent instance.
        Must be called before running chat turns.

        Raises:
            AgentExecutorError: If initialization fails
        """
        if self.mcp_server is not None:
            return  # Already initialized

        try:
            agent = self.GenericDatabaseMCPAgent(common_tables=self.common_tables)
            server_name = agent.get_server_name()

            # Setup environment for MCP server subprocess
            server_env = os.environ.copy()
            pythonpath_entries = list(self.local_import_path_strs)
            if existing := server_env.get("PYTHONPATH"):
                pythonpath_entries.append(existing)
            if pythonpath_entries:
                server_env["PYTHONPATH"] = os.pathsep.join(pythonpath_entries)

            # Build server arguments
            server_args = ["-m", "ds_mcp.server"]
            if server_name:
                server_args.extend(["--name", server_name])
            for table in self.common_tables:
                server_args.extend(["--table", table])

            # Create and start MCP server
            self.mcp_server = self.MCPServerStdio(
                name=server_name,
                params={"command": sys.executable, "args": server_args, "env": server_env},
                cache_tools_list=True,
                client_session_timeout_seconds=180.0,
                tool_filter=self.create_static_tool_filter(allowed_tool_names=self.exposed_tools),
            )
            await self.mcp_server.__aenter__()

            # Build agent instance
            self.agent_instance = agent.build(self.mcp_server)

        except Exception as e:
            raise AgentExecutorError(f"Failed to initialize agent: {e}") from e

    async def run_turn(
        self,
        user_message: str,
        conversation_items: list[dict[str, Any]] | None = None,
    ) -> tuple[str, dict[str, int], dict[str, int], float]:
        """
        Execute a single chat turn.

        Args:
            user_message: The user's message
            conversation_items: Previous conversation state (for multi-turn)

        Returns:
            Tuple of (response_text, tools_used, token_usage, time_taken_seconds)
            - response_text: Final agent response
            - tools_used: Dict mapping tool names to usage counts
            - token_usage: Dict with 'input_tokens', 'output_tokens', 'total_tokens'
            - time_taken_seconds: Execution time in seconds

        Raises:
            AgentExecutorError: If agent execution fails
        """
        if self.agent_instance is None:
            raise AgentExecutorError("Agent not initialized. Call initialize() first.")

        try:
            # Build input payload
            if conversation_items is None:
                input_payload = user_message
            else:
                input_payload = list(conversation_items)
                input_payload.append({"role": "user", "content": user_message})

            # Run agent
            t0 = time.perf_counter()
            result = await self.Runner.run(self.agent_instance, input=input_payload)
            dt = time.perf_counter() - t0

            # Store result for conversation state tracking
            self._last_result = result

            # Extract response text
            final_text = (result.final_output or "").strip()

            # Extract tools used
            tools = []
            for item in result.new_items:
                raw = getattr(item, "raw_item", None)
                name = getattr(raw, "name", None)
                if name:
                    tools.append(name)

            tools_used = dict(Counter(tools)) if tools else {}

            # Extract token usage
            token_usage = {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
            }
            for resp in result.raw_responses:
                if resp.usage:
                    token_usage["input_tokens"] += getattr(resp.usage, "input_tokens", 0) or 0
                    token_usage["output_tokens"] += getattr(resp.usage, "output_tokens", 0) or 0
                    token_usage["total_tokens"] += getattr(resp.usage, "total_tokens", 0) or 0

            return final_text, tools_used, token_usage, dt

        except Exception as e:
            raise AgentExecutorError(f"Agent execution failed: {e}") from e

    def get_conversation_items_for_next_turn(self) -> list[dict[str, Any]] | None:
        """
        Get updated conversation items for next turn based on last result.

        Returns:
            Conversation items list ready for next turn, or None if no prior turn
        """
        if self._last_result is None:
            return None
        return self._last_result.to_input_list()

    async def cleanup(self) -> None:
        """Cleanup MCP server resources."""
        if self.mcp_server is not None:
            try:
                await self.mcp_server.__aexit__(None, None, None)
            except Exception as e:
                print(f"Warning: Error cleaning up MCP server: {e}", file=sys.stderr)
            self.mcp_server = None
            self.agent_instance = None
            self._last_result = None

    async def __aenter__(self) -> AgentExecutor:
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.cleanup()
