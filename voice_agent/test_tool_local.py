"""Test script for oncograph_query tool without voice."""

import asyncio
import json
import logging
import os

from dotenv import load_dotenv

from voice_agent.handler import handle_query

# Load environment variables
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_tool():
    """Test the oncograph_query tool function directly."""
    test_queries = [
        "What causes resistance to cetuximab?",
        "What does vemurafenib target?",
        "Tell me about KRAS",
    ]

    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"Testing query: {query}")
        print(f"{'='*60}")

        try:
            result = await handle_query(query, speak_top_n=3)
            result_dict = result.model_dump()

            print(f"\nStatus: {result_dict['status']}")
            print(f"Confidence: {result_dict['confidence']}")
            print(f"Entities: {result_dict['entities']}")
            if result_dict.get("message"):
                print(f"Message: {result_dict['message']}")
            if result_dict.get("payload"):
                print(f"\nPayload (intent: {result_dict['payload']['intent']}):")
                print(json.dumps(result_dict["payload"], indent=2))
            else:
                print("No payload (status indicates no results or error)")

        except Exception as exc:
            logger.error(f"Test failed for query: {query}", exc_info=exc)
            print(f"ERROR: {exc}")


if __name__ == "__main__":
    asyncio.run(test_tool())

