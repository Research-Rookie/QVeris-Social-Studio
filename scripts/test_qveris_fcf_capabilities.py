"""Check whether QVeris exposes capabilities needed for FCF Yield.

This script only calls QVeris Discover/Inspect endpoints. It does not execute
paid capabilities. Set QVERIS_API_KEY locally before running.
"""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen


BASE_URL = os.environ.get("QVERIS_API_BASE_URL", "https://qveris.ai/api/v1")
API_KEY = os.environ.get("QVERIS_API_KEY")
QUERIES = [
    "quarterly free cash flow financial statements API",
    "market capitalization stock API",
    "company financial fundamentals cash flow market cap",
    "historical stock price market cap fundamentals",
]


def headers() -> dict[str, str]:
    if not API_KEY:
        raise RuntimeError("QVERIS_API_KEY is not set")
    return {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }


def post_json(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        f"{BASE_URL}{path}",
        data=body,
        headers=headers(),
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"QVeris API error {error.code} for {path}: {details}"
        ) from error


def compact_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "tool_id": result.get("tool_id"),
        "name": result.get("name"),
        "provider_name": result.get("provider_name"),
        "description": result.get("description"),
        "expected_cost": result.get("expected_cost"),
        "billing_rule": result.get("billing_rule"),
        "params": result.get("params"),
        "examples": result.get("examples"),
    }


def main() -> None:
    print(f"Base URL: {BASE_URL}")
    all_tool_ids: list[str] = []

    for query in QUERIES:
        payload = {
            "query": query,
            "limit": 5,
            "session_id": "qveris-social-studio-fcf-test",
        }
        data = post_json("/search", payload)
        results = data.get("results") or []
        print("\n" + "=" * 80)
        print(f"Query: {query}")
        print(f"Results: {len(results)}")

        for index, result in enumerate(results[:5], 1):
            compact = compact_result(result)
            tool_id = compact.get("tool_id")
            if tool_id and tool_id not in all_tool_ids:
                all_tool_ids.append(tool_id)
            print(f"\n#{index} {compact.get('name')} [{compact.get('provider_name')}]")
            print(f"tool_id: {tool_id}")
            print(f"description: {compact.get('description')}")
            print(f"expected_cost: {compact.get('expected_cost')}")

    if not all_tool_ids:
        print("\nNo candidate tools found.")
        return

    inspect_payload = {
        "tool_ids": all_tool_ids[:10],
        "session_id": "qveris-social-studio-fcf-test",
    }
    inspect_data = post_json("/tools/by-ids", inspect_payload)
    inspect_results = inspect_data.get("results") or []

    print("\n" + "=" * 80)
    print("Inspect summary")
    for result in inspect_results:
        compact = compact_result(result)
        print("\n" + json.dumps(compact, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
