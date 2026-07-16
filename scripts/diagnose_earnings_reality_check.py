"""Diagnose QVeris capabilities required by Earnings Reality Check."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from qveris_finance import execute_tool, expected_credits, fill_default_parameters, search_tools, walk_dicts


ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_FILE = ROOT_DIR / "data" / "earnings_reality_check_diagnostic.json"
SESSION_ID = "qveris-social-studio-earnings-reality-diagnostic"

QUERIES = [
    "US stock earnings calendar reported EPS estimated EPS actual revenue estimated revenue surprise",
    "company earnings results by ticker actual EPS estimate revenue estimate earnings date",
    "earnings surprises API actual EPS estimated EPS actual revenue estimated revenue",
    "historical earnings calendar with EPS estimate EPS actual revenue surprise",
    "US stock daily quote latest price change percent by symbol",
]

FIELD_GROUPS = {
    "symbol": ["symbol", "ticker"],
    "date": ["date", "fiscalDateEnding", "reportedDate", "earningsDate"],
    "eps_actual": ["epsActual", "actualEPS", "reportedEPS", "eps"],
    "eps_estimate": ["epsEstimated", "estimatedEPS", "epsEstimate", "consensusEPS"],
    "revenue_actual": ["revenueActual", "actualRevenue", "reportedRevenue", "revenue"],
    "revenue_estimate": ["revenueEstimated", "estimatedRevenue", "revenueEstimate", "consensusRevenue"],
    "surprise": ["surprise", "surprisePercentage", "epsSurprise", "epsSurprisePercent"],
    "price": ["price", "latestPrice", "currentPrice", "close"],
    "change_pct": ["changePercent", "changesPercentage", "percentChange"],
}


def normalize(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


def count_fields(payload: Any) -> dict[str, int]:
    groups = {name: {normalize(field) for field in fields} for name, fields in FIELD_GROUPS.items()}
    counts = {name: 0 for name in groups}
    for item in walk_dicts(payload):
        keys = {normalize(str(key)) for key in item}
        for name, aliases in groups.items():
            if keys & aliases:
                counts[name] += 1
    return counts


def samples(payload: Any, limit: int = 8) -> list[dict[str, Any]]:
    rows = []
    useful = {normalize(alias) for aliases in FIELD_GROUPS.values() for alias in aliases}
    useful |= {"name", "companyname", "period", "fiscalquarter", "fiscalyear"}
    for item in walk_dicts(payload):
        compact = {
            str(key): value
            for key, value in item.items()
            if normalize(str(key)) in useful and not isinstance(value, (dict, list))
        }
        if len(compact) >= 2 and compact not in rows:
            rows.append(compact)
        if len(rows) >= limit:
            break
    return rows


def main() -> None:
    today = datetime.now(timezone.utc).date()
    explicit = {
        "symbol": "AAPL",
        "ticker": "AAPL",
        "query": "AAPL recent earnings actual estimated EPS and revenue",
        "from": str(today - timedelta(days=120)),
        "to": str(today),
        "start_date": str(today - timedelta(days=120)),
        "end_date": str(today),
        "limit": 20,
        "market": "US",
    }
    tools: list[dict[str, Any]] = []
    probes: list[dict[str, Any]] = []
    seen: set[str] = set()
    for query in QUERIES:
        search_id, results = search_tools(query, SESSION_ID, limit=8)
        for result in results:
            tool_id = str(result.get("tool_id") or "")
            if not tool_id or tool_id in seen:
                continue
            seen.add(tool_id)
            record = {
                "query": query,
                "search_id": search_id,
                "name": result.get("name"),
                "tool_id": tool_id,
                "cost": expected_credits(result),
                "description": result.get("description"),
                "params": result.get("params") or [],
            }
            tools.append(record)

    ranked = sorted(tools, key=lambda row: (float(row.get("cost") or 0), row.get("name") or ""))
    for tool in ranked[:12]:
        record = {"name": tool["name"], "tool_id": tool["tool_id"], "cost": tool["cost"]}
        try:
            tool_meta = {"params": tool["params"]}
            parameters = fill_default_parameters(tool_meta, explicit)
            tool_name = str(tool.get("name") or "").lower()
            tool_id = str(tool.get("tool_id") or "").lower()
            if "earnings_estimates" in tool_id or "estimates" in tool_name:
                parameters = {"function": "EARNINGS_ESTIMATES", "symbol": "AAPL"}
            elif "alphavantage.earnings" in tool_id or "earnings history" in tool_name or tool_name == "retrieve earnings":
                parameters = {"function": "EARNINGS", "symbol": "AAPL"}
            elif "time-series.daily" in tool_id:
                parameters = {"function": "TIME_SERIES_DAILY", "symbol": "AAPL", "outputsize": "compact", "datatype": "json"}
            elif "yahoo finance earnings calendar" in tool_name:
                parameters = {"symbol": "AAPL", "time_range": "6m", "include_estimates": True, "max_results": 20}
            elif "finnhub.calendar.earnings" in tool_id:
                parameters = {"from": str(today - timedelta(days=120)), "to": str(today), "symbol": "AAPL", "international": False}
            elif "twelvedata.earnings" in tool_id:
                parameters = {"symbol": "AAPL", "period": "latest", "outputsize": 10, "format": "JSON"}
            payload = execute_tool(
                tool["tool_id"], SESSION_ID, parameters,
                search_id=tool["search_id"], max_response_size=65536,
            )
            record.update({
                "ok": True,
                "parameters": parameters,
                "field_counts": count_fields(payload),
                "samples": samples(payload),
                "raw_preview": json.dumps(payload, ensure_ascii=False)[:6000],
            })
        except Exception as error:
            record.update({"ok": False, "error": str(error)})
        probes.append(record)

    viable = [
        probe for probe in probes
        if probe.get("ok") and probe.get("field_counts", {}).get("eps_actual", 0)
        and probe.get("field_counts", {}).get("eps_estimate", 0)
    ]
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "searched_tools": tools,
        "probes": probes,
        "verdict": {
            "can_build": bool(viable),
            "viable_tools": [probe["tool_id"] for probe in viable],
            "note": "Requires actual and estimated EPS; revenue and price enrich the card when returned.",
        },
    }
    OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(output["verdict"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
