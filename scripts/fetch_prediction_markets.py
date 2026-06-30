"""Fetch prediction-market pulse data from QVeris."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from qveris_finance import (
    as_float,
    execute_tool,
    expected_credits,
    fill_default_parameters,
    search_tools,
    walk_dicts,
    walk_lists,
)


ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_FILE = ROOT_DIR / "data" / "prediction_markets.json"
RUN_TIMEZONE = ZoneInfo("Asia/Shanghai")
SESSION_ID = "qveris-social-studio-prediction-market-pulse"
QVERIS_PREDICTION_MARKET_TOOL_ID = os.environ.get("QVERIS_PREDICTION_MARKET_TOOL_ID", "")
LIMIT = int(os.environ.get("PREDICTION_MARKET_LIMIT", "8"))
SEARCH_QUERIES = [
    "Kalshi multivariate events include markets prices prediction markets",
    "Kalshi event markets yes price no price volume liquidity",
    "prediction market active markets with yes price no price probability volume liquidity",
    "Polymarket markets probability price volume liquidity",
]


def key_norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def value_by_names(item: dict, names: list[str]) -> object:
    normalized = {key_norm(str(key)): val for key, val in item.items()}
    for name in names:
        target = key_norm(name)
        if target in normalized:
            return normalized[target]
    return None


def clean_title(value: object) -> str:
    title = str(value or "").strip()
    return re.sub(r"\s+", " ", title)


def implied_probability(item: dict) -> float:
    direct = as_float(
        value_by_names(
            item,
            [
                "probability",
                "impliedProbability",
                "yesProbability",
                "chance",
                "lastPrice",
                "price",
                "yesPrice",
                "yes_price",
                "yes_bid",
                "yesBid",
                "yesAsk",
                "yes_ask",
                "last_price",
                "marketPrice",
                "market_price",
            ],
        )
    )
    if direct > 1:
        return min(100.0, direct)
    if direct > 0:
        return direct * 100
    return 0.0


def probability_change(item: dict) -> float:
    direct = as_float(
        value_by_names(
            item,
            [
                "probabilityChange",
                "probability_change",
                "change24h",
                "oneDayChange",
                "priceChange",
                "change",
            ],
        )
    )
    if abs(direct) <= 1 and direct != 0:
        return direct * 100
    return direct


def parse_market(item: dict) -> dict | None:
    title = clean_title(
        value_by_names(
            item,
            [
                "title",
                "name",
                "question",
                "eventTitle",
                "event_title",
                "marketTitle",
                "market_title",
                "subtitle",
                "shortTitle",
                "short_title",
            ],
        )
    )
    if not title:
        return None

    probability = implied_probability(item)
    has_probability = probability > 0
    if not has_probability:
        probability = 50.0

    ticker = str(
        value_by_names(
            item,
            [
                "ticker",
                "eventTicker",
                "event_ticker",
                "marketTicker",
                "market_ticker",
                "id",
                "slug",
            ],
        )
        or ""
    ).strip()
    category = str(
        value_by_names(
            item,
            [
                "category",
                "series",
                "seriesTicker",
                "series_ticker",
                "collectionTicker",
                "collection_ticker",
            ],
        )
        or "Prediction market"
    ).strip()
    volume = as_float(
        value_by_names(
            item,
            ["volume", "volume24h", "dailyVolume", "volume_24h", "daily_volume"],
        )
    )
    liquidity = as_float(value_by_names(item, ["liquidity", "openInterest", "open_interest"]))
    end_date = str(
        value_by_names(
            item,
            ["endDate", "end_date", "closeTime", "close_time", "expirationTime"],
        )
        or ""
    )
    status = str(value_by_names(item, ["status", "active", "isActive"]) or "").strip()

    return {
        "title": title,
        "ticker": ticker,
        "category": category,
        "probability": probability,
        "has_probability": has_probability,
        "probability_change": probability_change(item),
        "volume": volume,
        "liquidity": liquidity,
        "end_date": end_date,
        "status": status,
    }


def merge_event_market(event: dict, market: dict) -> dict:
    merged = dict(event)
    merged.update(market)
    if not value_by_names(merged, ["title", "name", "question", "marketTitle", "market_title"]):
        event_title = value_by_names(
            event,
            ["title", "name", "question", "eventTitle", "event_title", "shortTitle", "short_title"],
        )
        if event_title:
            merged["title"] = event_title
    if not value_by_names(merged, ["category", "series", "seriesTicker", "collectionTicker"]):
        category = value_by_names(event, ["category", "series", "seriesTicker", "collectionTicker"])
        if category:
            merged["category"] = category
    return merged


def parse_event_with_markets(item: dict) -> list[dict]:
    parsed = []
    for key, value in item.items():
        if not isinstance(value, list):
            continue
        if "market" not in str(key).lower() and "contract" not in str(key).lower():
            continue
        for child in value:
            if isinstance(child, dict):
                market = parse_market(merge_event_market(item, child))
                if market:
                    parsed.append(market)
    return parsed


def score_tool(tool: dict) -> int:
    text = " ".join(
        str(value or "")
        for value in [
            tool.get("name"),
            tool.get("tool_id"),
            tool.get("description"),
            tool.get("provider_name"),
            tool.get("provider"),
        ]
    ).lower()
    param_names = {
        str(param.get("name") or "").lower()
        for param in (tool.get("params") or [])
    }
    score = 0
    if "kalshi" in text:
        score += 8
    if "polymarket" in text:
        score += 6
    if "market" in text or "markets" in text:
        score += 8
    if "event" in text or "events" in text:
        score += 3
    if "multivariate" in text:
        score += 10
    if "price" in text or "probability" in text or "odds" in text:
        score += 8
    if "include_markets" in param_names or "include markets" in text:
        score += 14
    if "include_markets" in param_names and "multivariate" in text:
        score += 10
    if "series_ticker" in param_names:
        score += 5
    if "collection_ticker" in param_names:
        score += 5
    if "political" in text or "election" in text:
        score -= 8
    if "stock" in text or "financialmodelingprep" in text or "alphavantage" in text:
        score -= 20
    return score


def choose_prediction_tool() -> tuple[str, str, dict]:
    if QVERIS_PREDICTION_MARKET_TOOL_ID:
        return "", QVERIS_PREDICTION_MARKET_TOOL_ID, {
            "tool_id": QVERIS_PREDICTION_MARKET_TOOL_ID,
            "params": [],
        }

    best: tuple[int, float, str, dict] | None = None
    for query in SEARCH_QUERIES:
        search_id, results = search_tools(query, SESSION_ID, limit=10)
        for result in results:
            tool_id = result.get("tool_id")
            if not tool_id:
                continue
            cost = expected_credits(result)
            if cost and cost > 30:
                continue
            score = score_tool(result)
            if best is None or score > best[0]:
                best = (score, cost, search_id, result)

    if not best:
        raise RuntimeError("No QVeris prediction-market tool found")

    score, cost, search_id, selected = best
    print(
        "QVeris tool: "
        f"{selected.get('name')} ({selected['tool_id']}) score={score} cost={cost}"
    )
    return search_id, selected["tool_id"], selected


def execute_prediction_tool() -> dict:
    search_id, tool_id, tool = choose_prediction_tool()
    explicit = {
        "query": "active prediction market events markets probability price volume liquidity",
        "limit": LIMIT,
        "market": "US",
        "active": True,
        "include_markets": True,
        "includeMarkets": True,
    }
    parameters = explicit if QVERIS_PREDICTION_MARKET_TOOL_ID else fill_default_parameters(tool, explicit)
    for param in tool.get("params") or []:
        name = str(param.get("name") or "")
        lowered = name.lower()
        if lowered in {"include_markets", "includemarkets", "include_market"}:
            parameters[name] = True
        elif lowered in {"active", "include_markets"}:
            parameters[name] = True
        elif lowered == "limit":
            parameters[name] = LIMIT
    print(f"QVeris parameters: {parameters}")
    return execute_tool(
        tool_id,
        SESSION_ID,
        parameters,
        search_id=search_id,
        max_response_size=65536,
    )


def extract_markets(payload: dict) -> list[dict]:
    candidates = []
    seen = set()

    for collection in walk_lists(payload):
        if not collection or not all(isinstance(item, dict) for item in collection[: min(3, len(collection))]):
            continue
        for item in collection:
            if isinstance(item, dict):
                candidates.extend(parse_event_with_markets(item))
        parsed = [parse_market(item) for item in collection if isinstance(item, dict)]
        parsed = [item for item in parsed if item]
        if len(parsed) >= 2:
            candidates.extend(parsed)

    if not candidates:
        for item in walk_dicts(payload):
            candidates.extend(parse_event_with_markets(item))
            parsed = parse_market(item)
            if parsed:
                candidates.append(parsed)

    unique = []
    for market in candidates:
        identity = (market["ticker"] or market["title"]).lower().strip()
        identity = re.sub(r"[^a-z0-9]+", " ", identity)
        identity = re.sub(r"\s+", " ", identity).strip()
        if identity in seen:
            continue
        seen.add(identity)
        unique.append(market)

    unique.sort(
        key=lambda market: (
            abs(market.get("probability_change", 0)),
            market.get("volume", 0),
            market.get("liquidity", 0),
        ),
        reverse=True,
    )
    return unique[:LIMIT]


def fetch_prediction_market_payload() -> dict:
    return execute_prediction_tool()


def main() -> dict:
    raw = fetch_prediction_market_payload()
    markets = extract_markets(raw)
    if not markets:
        raise RuntimeError(
            "QVeris returned prediction-market data, but no event or market rows could be parsed."
        )

    now = datetime.now(timezone.utc)
    run_now = datetime.now(RUN_TIMEZONE)
    output = {
        "updated_at": now.isoformat(),
        "date": run_now.strftime("%Y-%m-%d"),
        "run_timezone": "Asia/Shanghai",
        "source": "QVeris API",
        "title": "Prediction Market Pulse",
        "markets": markets,
    }
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Saved {OUTPUT_FILE}")
    for index, market in enumerate(markets[:5], 1):
        print(
            f"  #{index} {market['probability']:.1f}% "
            f"({market['probability_change']:+.1f} pts) {market['title']}"
        )
    return output


if __name__ == "__main__":
    main()
