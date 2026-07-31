"""Rank QVeris finance capabilities using Discover routing signals."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from qveris_finance import expected_credits, search_tools


ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_FILE = ROOT_DIR / "data" / "api_reliability_arena.json"
RUN_TIMEZONE = ZoneInfo("Asia/Shanghai")
SESSION_ID = "qveris-social-studio-api-reliability-arena"

SCENARIOS = [
    {
        "key": "stock-quotes",
        "label": "Live U.S. stock quotes",
        "task": "Retrieve the latest U.S. stock price, change, and volume",
        "query": "real-time US stock quote API latest price change percent and volume",
    },
    {
        "key": "financial-news",
        "label": "Financial news signals",
        "task": "Retrieve current financial headlines, tickers, and sentiment",
        "query": "financial news API latest headlines ticker sentiment source published time",
    },
    {
        "key": "earnings",
        "label": "Company earnings results",
        "task": "Retrieve reported EPS, estimated EPS, and earnings surprise",
        "query": "company earnings results API actual EPS estimated EPS surprise reported date",
    },
    {
        "key": "sec-filings",
        "label": "SEC filing research",
        "task": "Retrieve recent 10-K, 10-Q, and 8-K filings for a company",
        "query": "SEC filings API company 10-K 10-Q 8-K accession filing date document URL",
    },
    {
        "key": "crypto-markets",
        "label": "Crypto market data",
        "task": "Retrieve crypto prices, market cap, and 24-hour volume",
        "query": "crypto market data API latest price market cap volume percent change",
    },
]


def number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        parsed = float(value)
        return parsed if math.isfinite(parsed) else None
    except (TypeError, ValueError):
        return None


def nested_number(item: dict[str, Any], paths: list[tuple[str, ...]]) -> float | None:
    for path in paths:
        current: Any = item
        for key in path:
            if not isinstance(current, dict) or key not in current:
                current = None
                break
            current = current[key]
        value = number(current)
        if value is not None:
            return value
    return None


def cost_known(tool: dict[str, Any]) -> bool:
    return any(
        tool.get(key) not in (None, "", {})
        for key in ("expected_cost", "cost", "billing_rule")
    )


def freshness_label(value: Any) -> str:
    if isinstance(value, bool):
        return "As-of supported" if value else "Not stated"
    if isinstance(value, dict):
        text = " ".join(str(part) for part in value.values() if part not in (None, ""))
    else:
        text = str(value or "")
    lowered = text.lower()
    if any(word in lowered for word in ("real-time", "realtime", "live")):
        return "Live capable"
    if text:
        return "As-of supported"
    return "Not stated"


def provider_label(tool: dict[str, Any]) -> str:
    explicit = str(tool.get("provider_name") or tool.get("provider") or "").strip()
    if explicit:
        return explicit
    tool_id = str(tool.get("tool_id") or "").lower()
    namespaces = {
        "financialmodelingprep": "Financial Modeling Prep",
        "alphavantage": "Alpha Vantage",
        "yahoo_finance": "Yahoo Finance",
        "finnhub": "Finnhub",
        "eodhd": "EODHD",
        "polygon": "Polygon",
        "twelvedata": "Twelve Data",
        "coingecko": "CoinGecko",
        "coinmarketcap": "CoinMarketCap",
        "sec.": "SEC EDGAR",
    }
    for namespace, label in namespaces.items():
        if tool_id.startswith(namespace):
            return label
    return "Provider not stated"


def normalize_tool(tool: dict[str, Any]) -> dict[str, Any]:
    stats = tool.get("stats") or {}
    success = nested_number(
        tool,
        [
            ("stats", "success_rate"),
            ("stats", "successRate"),
            ("reliability", "success_rate"),
            ("reliability", "successRate"),
        ],
    )
    if success is None:
        reliability = number(tool.get("reliability"))
        success = reliability
    if success is not None and success > 1:
        success /= 100
    if success is not None:
        success = max(0.0, min(1.0, success))

    latency = nested_number(
        tool,
        [
            ("stats", "avg_execution_time_ms"),
            ("stats", "average_execution_time_ms"),
            ("stats", "avg_latency_ms"),
            ("reliability", "avg_execution_time_ms"),
        ],
    )
    known_cost = cost_known(tool)
    cost = expected_credits(tool) if known_cost else None
    provider = provider_label(tool)
    name = str(tool.get("name") or tool.get("capability") or tool.get("tool_id") or "Unnamed capability")
    freshness = freshness_label(tool.get("as_of_support") or tool.get("asOfSupport"))

    success_component = success if success is not None else 0.45
    latency_component = 1 / (1 + max(latency or 1000, 1) / 1000)
    cost_component = 1 / (1 + max(cost or 2, 0) / 5)
    completeness = sum(value is not None for value in (success, latency, cost)) / 3
    route_score = (success_component * 0.55 + latency_component * 0.25 + cost_component * 0.20) * 100
    route_score *= 0.82 + completeness * 0.18

    return {
        "tool_id": str(tool.get("tool_id") or ""),
        "name": name,
        "provider": provider,
        "success_rate": success,
        "latency_ms": latency,
        "cost_credits": cost,
        "cost_known": known_cost,
        "freshness": freshness,
        "route_score": round(route_score, 1),
        "metric_count": int(completeness * 3),
        "expected_cost_text": str(tool.get("expected_cost") or ""),
    }


def main() -> dict[str, Any]:
    run_now = datetime.now(RUN_TIMEZONE)
    scenario = SCENARIOS[run_now.toordinal() % len(SCENARIOS)]
    search_id, results = search_tools(scenario["query"], SESSION_ID, limit=10)
    competitors = [normalize_tool(tool) for tool in results if tool.get("tool_id")]
    competitors.sort(
        key=lambda item: (item["metric_count"], item["route_score"], item["success_rate"] or 0),
        reverse=True,
    )
    competitors = competitors[:3]
    if len(competitors) < 2:
        raise RuntimeError(f"QVeris Discover returned fewer than two comparable tools: {len(competitors)}")
    for index, competitor in enumerate(competitors, start=1):
        competitor["rank"] = index

    champion = competitors[0]
    success_text = (
        f"{champion['success_rate'] * 100:.1f}% historical success"
        if champion.get("success_rate") is not None
        else "the strongest available routing profile"
    )
    takeaway = (
        f"QVeris ranks {champion['name']} first for {scenario['label'].lower()}, "
        f"led by {success_text}."
    )
    output = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "date": run_now.strftime("%Y-%m-%d"),
        "run_timezone": "Asia/Shanghai",
        "source": "QVeris Discover routing signals",
        "title": "API Reliability Arena",
        "scenario": scenario,
        "search_id": search_id,
        "result_count": len(results),
        "competitors": competitors,
        "champion": champion,
        "takeaway": takeaway,
        "methodology": {
            "success_weight": 0.55,
            "latency_weight": 0.25,
            "cost_weight": 0.20,
            "note": "Ranking uses QVeris historical routing signals; it is not a live load test.",
        },
    }
    OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {OUTPUT_FILE}")
    print(f"Scenario: {scenario['label']}")
    for item in competitors:
        print(f"  #{item['rank']} {item['name']} ({item['provider']}) score={item['route_score']}")
    return output


if __name__ == "__main__":
    main()
