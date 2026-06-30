"""Fetch prediction-market pulse data from QVeris."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from qveris_finance import as_float, execute_best_tool, walk_dicts, walk_lists


ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_FILE = ROOT_DIR / "data" / "prediction_markets.json"
RUN_TIMEZONE = ZoneInfo("Asia/Shanghai")
SESSION_ID = "qveris-social-studio-prediction-market-pulse"
QVERIS_PREDICTION_MARKET_TOOL_ID = os.environ.get("QVERIS_PREDICTION_MARKET_TOOL_ID", "")
LIMIT = int(os.environ.get("PREDICTION_MARKET_LIMIT", "8"))


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


def extract_markets(payload: dict) -> list[dict]:
    candidates = []
    seen = set()

    for collection in walk_lists(payload):
        if not collection or not all(isinstance(item, dict) for item in collection[: min(3, len(collection))]):
            continue
        parsed = [parse_market(item) for item in collection if isinstance(item, dict)]
        parsed = [item for item in parsed if item]
        if len(parsed) >= 2:
            candidates.extend(parsed)

    if not candidates:
        for item in walk_dicts(payload):
            parsed = parse_market(item)
            if parsed:
                candidates.append(parsed)

    unique = []
    for market in candidates:
        identity = market["ticker"] or market["title"].lower()
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
    query = (
        "Active prediction market events or markets with title, ticker, current probability or price, "
        "volume, liquidity, status, and close date"
    )
    return execute_best_tool(
        query,
        SESSION_ID,
        {
            "query": "active prediction market events markets probability price volume liquidity",
            "limit": LIMIT,
            "market": "US",
            "active": True,
            "include_markets": True,
        },
        configured_tool_id=QVERIS_PREDICTION_MARKET_TOOL_ID,
        max_response_size=65536,
    )


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
