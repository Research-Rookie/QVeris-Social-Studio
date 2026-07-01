"""Diagnose whether QVeris can power a Financial News Signal column."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from qveris_finance import execute_tool, search_tools, walk_dicts


ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_FILE = ROOT_DIR / "data" / "financial_news_capability_diagnostic.json"
SESSION_ID = "qveris-social-studio-financial-news-diagnostic"

QUERIES = [
    "financial news API latest market headlines ticker sentiment",
    "stock market news by ticker with headline source published date sentiment",
    "financial news sentiment API for US stocks",
    "market news API top financial headlines today",
    "company news API ticker articles published date source url",
]

EXECUTION_PROBES = [
    {
        "label": "latest_market_news",
        "query_match": "financial news",
        "parameters": {"query": "latest US stock market news", "limit": 5},
    },
    {
        "label": "ticker_news_aapl",
        "query_match": "stock market news by ticker",
        "parameters": {"symbol": "AAPL", "ticker": "AAPL", "query": "AAPL news", "limit": 5},
    },
]

FIELD_GROUPS = {
    "headline": ["headline", "title", "name"],
    "summary": ["summary", "description", "content", "text"],
    "url": ["url", "link", "articleUrl", "newsUrl"],
    "source": ["source", "publisher", "site", "provider"],
    "published_at": ["publishedAt", "published_at", "date", "datetime", "time"],
    "ticker": ["ticker", "symbol", "stock"],
    "sentiment": ["sentiment", "sentimentScore", "score", "polarity"],
}


def normalize(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


def expected_credits(tool: dict[str, Any]) -> float:
    billing_rule = tool.get("billing_rule") or {}
    price = billing_rule.get("price") or {}
    candidates = [
        tool.get("cost"),
        billing_rule.get("amount_credits"),
        billing_rule.get("amount"),
        price.get("amount_credits") if isinstance(price, dict) else None,
    ]
    for value in candidates:
        if value in (None, ""):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            pass
    return 0.0


def count_fields(payload: Any) -> dict[str, int]:
    counters = {name: 0 for name in FIELD_GROUPS}
    normalized_groups = {
        name: {normalize(field) for field in fields}
        for name, fields in FIELD_GROUPS.items()
    }
    for item in walk_dicts(payload):
        keys = {normalize(str(key)) for key in item}
        for group_name, group_keys in normalized_groups.items():
            if keys & group_keys:
                counters[group_name] += 1
    return counters


def sample_rows(payload: Any, limit: int = 4) -> list[dict[str, str]]:
    rows = []
    for item in walk_dicts(payload):
        compact = {}
        for key, value in item.items():
            if isinstance(value, (dict, list)):
                continue
            text = str(value)
            if text:
                compact[str(key)] = text[:180] + ("..." if len(text) > 180 else "")
        if compact:
            rows.append(compact)
        if len(rows) >= limit:
            break
    return rows


def search_capabilities() -> list[dict[str, Any]]:
    results = []
    seen = set()
    for query in QUERIES:
        search_id, tools = search_tools(query, SESSION_ID, limit=10)
        for tool in tools:
            tool_id = tool.get("tool_id")
            if not tool_id or tool_id in seen:
                continue
            seen.add(tool_id)
            results.append(
                {
                    "query": query,
                    "search_id": search_id,
                    "name": tool.get("name"),
                    "tool_id": tool_id,
                    "provider": tool.get("provider_name") or tool.get("provider"),
                    "expected_credits": expected_credits(tool),
                    "description": tool.get("description"),
                    "params": tool.get("params") or [],
                }
            )
    return results


def choose_probe_tool(tools: list[dict[str, Any]], query_match: str) -> dict[str, Any] | None:
    ranked = []
    needle = query_match.lower()
    for tool in tools:
        haystack = " ".join(
            str(tool.get(field) or "")
            for field in ["query", "name", "description", "tool_id"]
        ).lower()
        if needle not in haystack:
            continue
        cost = float(tool.get("expected_credits") or 0)
        ranked.append((cost, tool))
    if not ranked:
        return None
    ranked.sort(key=lambda item: item[0])
    return ranked[0][1]


def execute_probes(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    probes = []
    for probe in EXECUTION_PROBES:
        tool = choose_probe_tool(tools, probe["query_match"])
        if not tool:
            probes.append({"label": probe["label"], "ok": False, "error": "No matching tool found"})
            continue
        record = {
            "label": probe["label"],
            "tool_id": tool["tool_id"],
            "tool_name": tool.get("name"),
            "expected_credits": tool.get("expected_credits"),
            "parameters": probe["parameters"],
        }
        try:
            payload = execute_tool(
                tool["tool_id"],
                SESSION_ID,
                probe["parameters"],
                search_id=tool.get("search_id") or "",
                max_response_size=65536,
            )
            record["ok"] = True
            record["field_counts"] = count_fields(payload)
            record["samples"] = sample_rows(payload)
            record["raw_type"] = type(payload).__name__
        except RuntimeError as error:
            record["ok"] = False
            record["error"] = str(error)
        probes.append(record)
    return probes


def verdict(tools: list[dict[str, Any]], probes: list[dict[str, Any]]) -> dict[str, Any]:
    totals = Counter()
    for probe in probes:
        if probe.get("ok"):
            totals.update(probe.get("field_counts") or {})
    can_headline_feed = totals["headline"] > 0 and totals["url"] > 0
    can_ticker_news = any(
        probe.get("ok") and probe.get("label") == "ticker_news_aapl"
        for probe in probes
    )
    can_sentiment = totals["sentiment"] > 0
    return {
        "searched_tool_count": len(tools),
        "can_financial_news_signal": can_headline_feed or can_ticker_news,
        "can_headline_feed": can_headline_feed,
        "can_ticker_news": can_ticker_news,
        "can_sentiment": can_sentiment,
        "field_totals": dict(totals),
        "recommendation": (
            "Build Financial News Signal with headline + ticker-news cards; sentiment can be included if available."
            if can_headline_feed or can_ticker_news
            else "Search found candidates, but execution did not return enough article fields yet."
        ),
    }


def main() -> dict[str, Any]:
    tools = search_capabilities()
    probes = execute_probes(tools)
    output = {
        "searched_tools": tools,
        "probes": probes,
        "verdict": verdict(tools, probes),
    }
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {OUTPUT_FILE}")
    print(json.dumps(output["verdict"], ensure_ascii=False, indent=2))
    return output


if __name__ == "__main__":
    main()
