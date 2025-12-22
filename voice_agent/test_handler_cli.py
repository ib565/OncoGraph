#!/usr/bin/env python3
"""CLI script for testing handle_query function.

Usage:
    python -m voice_agent.test_handler_cli "What causes resistance to cetuximab?"
    echo "What therapies target BRAF?" | python -m voice_agent.test_handler_cli
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from dotenv import load_dotenv

from voice_agent.handler import handle_query


class _MetricsDefaultsFilter(logging.Filter):
    """Ensure timing/intent fields exist on all records used by the CLI formatter.

    Third‑party libraries (httpx, google.genai, etc.) don't know about our
    custom fields, so the formatter must not fail when they are missing.
    """

    _FIELDS = ("intent", "router_ms", "template_ms", "cypher_ms", "formatting_ms", "total_ms", "latency_ms")

    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        for field in self._FIELDS:
            if not hasattr(record, field):
                setattr(record, field, "")
        return True


load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s %(levelname)s %(name)s "
        "intent=%(intent)s "
        "router_ms=%(router_ms)s template_ms=%(template_ms)s "
        "cypher_ms=%(cypher_ms)s formatting_ms=%(formatting_ms)s "
        "total_ms=%(total_ms)s latency_ms=%(latency_ms)s %(message)s"
    ),
    force=True,
)

# Attach a filter so that logs from libraries without our custom fields
# still render correctly with the same formatter.
for _handler in logging.getLogger().handlers:
    _handler.addFilter(_MetricsDefaultsFilter())


async def main() -> int:
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(description="Test the OncoGraph voice handler tool.")
    parser.add_argument(
        "query",
        nargs="*",
        help="Natural language query. If omitted, read from stdin.",
    )
    parser.add_argument(
        "--speak-top-n",
        type=int,
        default=3,
        help="Maximum number of top items to include in payload lists (default: 3).",
    )
    args = parser.parse_args()

    if args.query:
        query = " ".join(args.query)
    else:
        query = sys.stdin.read().strip()

    if not query:
        print("Error: No query provided", file=sys.stderr)
        print("Usage: python -m voice_agent.test_handler_cli 'your query here'", file=sys.stderr)
        return 1

    print(f"Query: {query}\n")

    try:
        result = await handle_query(query, speak_top_n=args.speak_top_n)
        print(result.model_dump_json(indent=2))
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
