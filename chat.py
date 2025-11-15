#!/usr/bin/env python3
"""
Interactive chat interface using GenericDatabaseMCPAgent.

Type '/exit' to quit.
"""

from __future__ import annotations

import asyncio
import sys

from agent_core import AgentExecutor, AgentExecutorError


async def chat() -> int:
    """Run interactive chat with GenericDatabaseMCPAgent."""
    print(f"Starting MCP server …", file=sys.stderr)

    try:
        async with AgentExecutor() as executor:
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

                # Run the agent turn
                final_text, tools_used, token_usage, dt = await executor.run_turn(
                    user, conversation_items
                )

                # Print final output
                print("Assistant:")
                print(final_text if final_text else "<no output>")

                # Print stats (tools + tokens)
                if tools_used:
                    print(f"[tools] {tools_used}")
                if token_usage.get("total_tokens", 0) > 0:
                    print(
                        f"[usage] in={token_usage['input_tokens']}, "
                        f"out={token_usage['output_tokens']}, "
                        f"total={token_usage['total_tokens']}"
                    )
                print(f"[time] {dt:.2f}s\n")

                # Update conversation state for next turn
                conversation_items = executor.get_conversation_items_for_next_turn()

    except AgentExecutorError as e:
        print(f"\nError: Failed to run agent", file=sys.stderr)
        print(f"Details: {e}", file=sys.stderr)
        if "connection time out" in str(e).lower() or "timeout" in str(e).lower():
            print("\nTroubleshooting tips:", file=sys.stderr)
            print("  1. Connect to VPN", file=sys.stderr)
            print("  2. Verify database credentials are configured", file=sys.stderr)
            print("  3. Check network connectivity", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\nUnexpected error: {e}", file=sys.stderr)
        return 1

    return 0


def main() -> int:
    return asyncio.run(chat())


if __name__ == "__main__":
    raise SystemExit(main())
