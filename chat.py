#!/usr/bin/env python3
"""
Interactive chat interface for DS-MCP tables.

Every table automatically exposes describe_table(), get_table_schema(),
read_table_head(), and query_table(), plus any bespoke SQL helpers (e.g.,
provider macros). Use --table to point at any slug or schema.table string and
pick the agent instructions that fit your workflow.

Type '/exit' to quit.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

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
from ds_agents.mcp_agents import (
    GenericDatabaseMCPAgent,
    MarketAnomaliesMCPAgent,
    ProviderAuditMCPAgent,
)
from ds_mcp.tables import get_table, list_available_tables


AGENT_CLASSES = {
    "provider": ProviderAuditMCPAgent,
    "anomalies": MarketAnomaliesMCPAgent,
    "generic": GenericDatabaseMCPAgent,
}

TABLE_PROFILES = {
    "provider": ["provider"],
    "anomalies": ["anomalies"],
}


def _summarize_tables(table_ids: list[str]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for identifier in table_ids:
        table = get_table(identifier)
        summaries.append(
            {
                "identifier": identifier,
                "full_name": table.full_name,
                "custom_tools": [spec.name for spec in table.custom_tools],
                "query_aliases": list(table.query_aliases),
            }
        )
    return summaries


async def chat(agent_kind: str, tables: list[str], allow_query_table: bool, server_label: str | None = None) -> int:
    # Resolve agent + MCP stdio script + default macro tools
    agent_cls = AGENT_CLASSES.get(agent_kind)
    if not agent_cls:
        raise ValueError(f"Unknown agent kind: {agent_kind}")

    # Pull defaults from the agent class
    agent_oop = agent_cls()
    table_summaries = _summarize_tables(tables)
    print("Configured tables:")
    for summary in table_summaries:
        print(f"- {summary['identifier']} → {summary['full_name']}")
        base = ["describe_table", "get_table_schema", "read_table_head"]
        print(f"  Base tools: {', '.join(base)}")
        if summary["custom_tools"]:
            print(f"  Custom tools: {', '.join(summary['custom_tools'])}")
        if summary["query_aliases"]:
            print(f"  Query aliases: {', '.join(summary['query_aliases'])}")
    print()

    allowed_tools = agent_oop.allowed_tool_names()
    if not allow_query_table:
        disallowed = {"query_table"}
        for summary in table_summaries:
            disallowed.update(summary["query_aliases"])
        allowed_tools = [tool for tool in allowed_tools if tool not in disallowed]
    server_name = server_label or agent_oop.get_server_name()

    print(f"Starting MCP server for {agent_kind} …", file=sys.stderr)
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
    for table in tables:
        server_args.extend(["--table", table])

    async with MCPServerStdio(
        name=server_name,
        params={"command": sys.executable, "args": server_args, "env": server_env},
        cache_tools_list=True,
        client_session_timeout_seconds=180.0,
        tool_filter=create_static_tool_filter(allowed_tool_names=allowed_tools),
    ) as server:
        agent = agent_oop.build(server)

        # Manual conversation management using to_input_list()
        # See: docs/running_agents.md → Manual conversation management
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
                # Append user message to prior items
                input_payload = list(conversation_items)
                input_payload.append({"role": "user", "content": user})

            t0 = time.perf_counter()
            result = await Runner.run(agent, input=input_payload)
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

    return 0


def _prompt_generic_tables() -> list[str]:
    available = list_available_tables()
    if not available:
        print("No tables discovered. Enter at least one identifier (schema.table).")
    for idx, (slug, display) in enumerate(available, start=1):
        print(f"[{idx}] {slug} – {display}")
    print("[A] Add custom table identifier (schema.table or database.schema.table)")
    print("[ALL] Enable all listed tables")
    print("Press Enter with no input when done.")

    selections: list[str] = []
    slug_lookup = {str(i + 1): slug for i, (slug, _) in enumerate(available)}

    while True:
        choice = input("Select option: ").strip()
        if not choice:
            break
        upper = choice.upper()
        if upper == "ALL":
            selections = [slug for slug, _ in available]
            break
        if upper == "A":
            identifier = input("Enter schema.table (or database.schema.table): ").strip()
            if identifier:
                selections.append(identifier)
            continue
        slug = slug_lookup.get(choice)
        if slug:
            selections.append(slug)
            continue
        print("Unrecognized option. Try again.")

    if not selections:
        print("No explicit selection made; defaulting to all discovered tables.")
        selections = [slug for slug, _ in available]
    deduped: list[str] = []
    seen: set[str] = set()
    for item in selections:
        if item not in seen:
            deduped.append(item)
            seen.add(item)
    return deduped


def main() -> int:
    parser = argparse.ArgumentParser(description="Interactive chat for DS-MCP tables (schema/head/query tools built-in)")
    parser.add_argument("--agent", choices=list(AGENT_CLASSES.keys()), default="provider", help="Which agent instructions to use")
    parser.add_argument(
        "--allow-query-table",
        action="store_true",
        help="Permit direct query_table()/query_* aliases (off by default)",
    )
    args = parser.parse_args()

    if args.agent == "generic":
        tables = _prompt_generic_tables()
    else:
        tables = list(TABLE_PROFILES.get(args.agent, ()))
        if not tables:
            parser.error("No tables configured for this agent. Update TABLE_PROFILES in chat.py.")

    return asyncio.run(chat(args.agent, tables, args.allow_query_table))


if __name__ == "__main__":
    raise SystemExit(main())
