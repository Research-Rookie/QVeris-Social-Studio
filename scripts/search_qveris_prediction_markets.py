"""Search QVeris for prediction-market capabilities.

This script only calls QVeris /search. It does not execute paid tools.
Use it to check whether QVeris can discover Polymarket / prediction-market
data for a World Cup probability column.
"""

from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BASE_URL = os.environ.get("QVERIS_API_BASE_URL", "https://qveris.ai/api/v1").rstrip("/")
API_KEY = os.environ.get("QVERIS_API_KEY")
SESSION_ID = "qveris-social-studio-prediction-market-search"
QUERIES = [
    "Polymarket World Cup winner probability market",
    "prediction market World Cup winner odds probability",
    "Polymarket sports market event odds volume liquidity",
    "World Cup outright winner betting market implied probability",
    "prediction market historical probability time series by event",
]


def post_search(query: str) -> dict:
    if not API_KEY:
        raise RuntimeError(
            "QVERIS_API_KEY is not set. In PowerShell, run: "
            '$env:QVERIS_API_KEY="your_key_here"'
        )
    payload = {
        "query": query,
        "limit": 8,
        "session_id": SESSION_ID,
    }
    request = Request(
        f"{BASE_URL}/search",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"QVeris HTTP {error.code}: {details}") from error
    except URLError as error:
        raise RuntimeError(f"Could not connect to QVeris API: {error}") from error


def compact_tool(result: dict) -> dict:
    billing_rule = result.get("billing_rule") or {}
    price = billing_rule.get("price") or {}
    cost = (
        result.get("expected_cost")
        or price.get("amount_credits")
        or billing_rule.get("amount_credits")
        or "cost not shown"
    )
    params = [
        {
            "name": param.get("name"),
            "type": param.get("type"),
            "required": param.get("required"),
        }
        for param in (result.get("params") or [])
    ]
    return {
        "name": result.get("name"),
        "provider": result.get("provider_name") or result.get("provider"),
        "tool_id": result.get("tool_id"),
        "cost": cost,
        "description": result.get("description"),
        "params": params,
    }


def main() -> None:
    print(f"Base URL: {BASE_URL}")
    for query in QUERIES:
        print("\n" + "=" * 88)
        print(f"Query: {query}")
        data = post_search(query)
        results = data.get("results") or []
        print(f"Search results: {len(results)}")
        for index, result in enumerate(results, 1):
            tool = compact_tool(result)
            print(f"\n#{index} {tool['name']} | {tool['provider']} | {tool['tool_id']}")
            print(f"Cost: {tool['cost']}")
            print(f"Description: {tool['description']}")
            print(f"Params: {tool['params']}")


if __name__ == "__main__":
    main()
