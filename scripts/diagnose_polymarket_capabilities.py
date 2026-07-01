"""Diagnose whether QVeris can power Polymarket theme/market breakdowns."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from qveris_finance import execute_tool, search_tools, walk_dicts


ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_FILE = ROOT_DIR / "data" / "polymarket_capability_diagnostic.json"
SESSION_ID = "qveris-social-studio-polymarket-diagnostic"

QUERIES = [
    "Polymarket markets list events category volume open interest",
    "Polymarket open interest markets title category",
    "Polymarket series events markets categories volume",
    "Polymarket market activity categories events",
]

EXECUTION_PROBES = [
    {
        "label": "open_interest",
        "tool_id": "polymarket.open_interest.list.v1.f613174f",
        "parameters": {},
    },
    {
        "label": "series",
        "tool_id": "polymarket.series.list.v1.7e5c1eeb",
        "parameters": {},
    },
    {
        "label": "markets_volume",
        "tool_id": "polymarket.gamma_get_markets.v1",
        "parameters": {
            "limit": 20,
            "order": "volumeNum",
            "ascending": False,
            "active": True,
            "closed": False,
        },
    },
    {
        "label": "events_volume",
        "tool_id": "polymarket.events.list.v1.eafcc524",
        "parameters": {
            "limit": 20,
            "order": "volume",
            "ascending": False,
            "volume_min": 1000,
            "active": True,
            "closed": False,
        },
    },
    {
        "label": "builder_volume_day",
        "tool_id": "polymarket.builders.volume.list.v1.38f84687",
        "parameters": {"timePeriod": "day"},
    },
    {
        "label": "builder_volume_no_params",
        "tool_id": "polymarket.builders.volume.list.v1.38f84687",
        "parameters": {},
    },
]

FIELD_GROUPS = {
    "title": ["title", "question", "name", "slug", "market", "event"],
    "category": ["category", "categories", "tag", "tags", "series", "collection"],
    "volume": ["volume", "dailyVolume", "totalVolume", "amount"],
    "open_interest": ["openInterest", "open_interest", "oi"],
    "market_id": ["id", "market", "marketId", "conditionId"],
}


def normalize(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


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


def sample_rows(payload: Any, limit: int = 3) -> list[dict[str, Any]]:
    samples = []
    for item in walk_dicts(payload):
        if not isinstance(item, dict) or not item:
            continue
        compact = {}
        for key, value in item.items():
            if isinstance(value, (dict, list)):
                continue
            text = str(value)
            compact[str(key)] = text[:140] + ("..." if len(text) > 140 else "")
        if compact:
            samples.append(compact)
        if len(samples) >= limit:
            break
    return samples


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
                    "cost": tool.get("cost"),
                    "description": tool.get("description"),
                    "params": tool.get("params") or [],
                }
            )
    return results


def execute_probes() -> list[dict[str, Any]]:
    probe_results = []
    for probe in EXECUTION_PROBES:
        record = dict(probe)
        try:
            payload = execute_tool(
                probe["tool_id"],
                SESSION_ID,
                probe["parameters"],
                max_response_size=65536,
            )
            record["ok"] = True
            record["field_counts"] = count_fields(payload)
            record["samples"] = sample_rows(payload)
            record["raw_type"] = type(payload).__name__
        except RuntimeError as error:
            record["ok"] = False
            record["error"] = str(error)
        probe_results.append(record)
    return probe_results


def verdict(probes: list[dict[str, Any]]) -> dict[str, Any]:
    totals = Counter()
    for probe in probes:
        if probe.get("ok"):
            totals.update(probe.get("field_counts") or {})
    can_market_breakdown = totals["title"] > 0 and (
        totals["volume"] > 0 or totals["open_interest"] > 0
    )
    can_theme_breakdown = totals["category"] > 0 and (
        totals["volume"] > 0 or totals["open_interest"] > 0
    )
    return {
        "can_market_breakdown": can_market_breakdown,
        "can_theme_breakdown": can_theme_breakdown,
        "field_totals": dict(totals),
        "recommendation": (
            "Use market-level and theme-level cards."
            if can_market_breakdown and can_theme_breakdown
            else "Use market-level cards only."
            if can_market_breakdown
            else "Keep the current aggregate activity card."
        ),
    }


def main() -> dict[str, Any]:
    output = {
        "searched_tools": search_capabilities(),
        "probes": execute_probes(),
    }
    output["verdict"] = verdict(output["probes"])
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {OUTPUT_FILE}")
    print(json.dumps(output["verdict"], ensure_ascii=False, indent=2))
    return output


if __name__ == "__main__":
    main()
