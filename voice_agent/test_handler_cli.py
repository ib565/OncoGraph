#!/usr/bin/env python3
"""CLI script for testing handle_query function.

Usage:
    python -m voice_agent.test_handler_cli "What causes resistance to cetuximab?"
    echo "What therapies target BRAF?" | python -m voice_agent.test_handler_cli
"""

from __future__ import annotations

import asyncio
import sys
from dotenv import load_dotenv

from voice_agent.handler import handle_query

load_dotenv()


async def main() -> int:
    """Main entry point for CLI."""
    # Get query from command line argument or stdin
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    else:
        query = sys.stdin.read().strip()

    if not query:
        print("Error: No query provided", file=sys.stderr)
        print("Usage: python -m voice_agent.test_handler_cli 'your query here'", file=sys.stderr)
        return 1

    print(f"Query: {query}\n")

    try:
        response = await handle_query(query)
        print(f"Response: {response}")
        return 0
    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
