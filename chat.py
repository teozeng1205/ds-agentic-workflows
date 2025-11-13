#!/usr/bin/env python3
"""
Interactive chat interface using GenericDatabaseMCPAgent.

Type '/exit' to quit.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from collections import Counter
from pathlib import Path

# Ensure local submodules are importable without pip installs
REPO_ROOT = Path(__file__).resolve().parent
LOCAL_IMPORT_PATHS = [
    REPO_ROOT / "ds-agents",
    REPO_ROOT / "ds-mcp" / "src",
]
LOCAL_IMPORT_PATH_STRS = []
for _path in LOCAL_IMPORT_PATHS:
    if _path.exists():
        _str_path = str(_path)
        LOCAL_IMPORT_PATH_STRS.append(_str_path)
        if _str_path not in sys.path:
            sys.path.insert(0, _str_path)

from agents import Runner
from agents.mcp import MCPServerStdio, create_static_tool_filter
from ds_agents.mcp_agents import GenericDatabaseMCPAgent

# Core tools exposed to the agent
EXPOSED_TOOLS = [
#  "describe_table",
#  "get_table_schema",
    "read_table_head",
    "query_table",
    "get_top_site_issues",
    "analyze_issue_scope",
]


async def chat() -> int:
    """Run interactive chat with GenericDatabaseMCPAgent."""
    agent = GenericDatabaseMCPAgent()

    server_name = agent.get_server_name()

    print(f"Starting MCP server …", file=sys.stderr)
    # Ensure the MCP server uses the same Python interpreter and env as this process
    server_env = os.environ.copy()
    pythonpath_entries = list(LOCAL_IMPORT_PATH_STRS)
    if existing := server_env.get("PYTHONPATH"):
        pythonpath_entries.append(existing)
    if pythonpath_entries:
        server_env["PYTHONPATH"] = os.pathsep.join(pythonpath_entries)

    server_args = ["-m", "ds_mcp.server"]
    if server_name:
        server_args.extend(["--name", server_name])

    try:
        async with MCPServerStdio(
            name=server_name,
            params={"command": sys.executable, "args": server_args, "env": server_env},
            cache_tools_list=True,
            client_session_timeout_seconds=180.0,
            tool_filter=create_static_tool_filter(allowed_tool_names=EXPOSED_TOOLS),
        ) as server:
            agent_instance = agent.build(server)

            conversation_items = None  # type: list | None

            print("Chat ready. Type /exit to quit.\n")
            while True:
                try:
                    user = input("You: ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\nBye.")
                    return 0

                if not user:
                    continue
                if user.lower() in {"/exit", ":q", ":quit", ":exit"}:
                    print("Bye.")
                    return 0

                # Build the input payload for this turn
                if conversation_items is None:
                    input_payload = user
                else:
                    input_payload = list(conversation_items)
                    input_payload.append({"role": "user", "content": user})

                t0 = time.perf_counter()
                result = await Runner.run(agent_instance, input=input_payload)
                dt = time.perf_counter() - t0

                # Print final output
                final_text = (result.final_output or "").strip()
                print("Assistant:")
                print(final_text if final_text else "<no output>")

                # Lightweight stats (tools + tokens)
                tools = []
                for item in result.new_items:
                    raw = getattr(item, "raw_item", None)
                    name = getattr(raw, "name", None)
                    if name:
                        tools.append(name)
                if tools:
                    counts = dict(Counter(tools))
                    print(f"[tools] {counts}")
                # Token usage (if available for this model/provider)
                total_in = total_out = total = 0
                for resp in result.raw_responses:
                    if resp.usage:
                        total_in += getattr(resp.usage, "input_tokens", 0) or 0
                        total_out += getattr(resp.usage, "output_tokens", 0) or 0
                        total += getattr(resp.usage, "total_tokens", 0) or 0
                if total:
                    print(f"[usage] in={total_in}, out={total_out}, total={total}")
                print(f"[time] {dt:.2f}s\n")

                # Update conversation state for next turn
                conversation_items = result.to_input_list()

    except Exception as e:
        print(f"\nError: Failed to start MCP server", file=sys.stderr)
        print(f"Details: {e}", file=sys.stderr)
        if "connection time out" in str(e).lower() or "timeout" in str(e).lower():
            print("\nTroubleshooting tips:", file=sys.stderr)
            print("  1. Connect to VPN", file=sys.stderr)
            print("  2. Verify database credentials are configured", file=sys.stderr)
            print("  3. Check network connectivity", file=sys.stderr)
        return 1

    return 0


def main() -> int:
    return asyncio.run(chat())


if __name__ == "__main__":
    raise SystemExit(main())
