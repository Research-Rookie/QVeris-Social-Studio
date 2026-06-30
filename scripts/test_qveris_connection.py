"""Low-risk QVeris API connection test.

This script verifies:
- QVERIS_API_KEY is visible to the process.
- The configured QVeris REST API base URL is reachable.
- /search returns finance-related capabilities.

It does not execute paid tools.
"""

from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BASE_URL = os.environ.get("QVERIS_API_BASE_URL", "https://qveris.ai/api/v1").rstrip("/")
API_KEY = os.environ.get("QVERIS_API_KEY")


def main() -> None:
    if not API_KEY:
        raise RuntimeError(
            "QVERIS_API_KEY is not set. In PowerShell, run: "
            '$env:QVERIS_API_KEY="your_key_here"'
        )

    payload = {
        "query": "US stock quote and market data API",
        "limit": 3,
        "session_id": "qveris-social-studio-connection-test",
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
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"QVeris HTTP {error.code}: {details}") from error
    except URLError as error:
        raise RuntimeError(f"Could not connect to QVeris API: {error}") from error

    results = data.get("results") or []
    print("QVeris API connection: OK")
    print(f"Base URL: {BASE_URL}")
    print(f"Search results: {len(results)}")
    for index, result in enumerate(results, 1):
        name = result.get("name") or "Unnamed capability"
        provider = result.get("provider_name") or result.get("provider") or "Unknown provider"
        tool_id = result.get("tool_id") or "no tool_id"
        expected_cost = result.get("expected_cost") or result.get("billing_rule") or "cost not shown"
        print(f"{index}. {name} | {provider} | {tool_id} | {expected_cost}")


if __name__ == "__main__":
    main()
