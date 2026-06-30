"""Fetch the daily Top 5 U.S. stock gainers from QVeris."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from qveris_finance import as_float, execute_best_tool, walk_dicts, walk_lists


ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_FILE = ROOT_DIR / "data" / "rankings.json"
RUN_TIMEZONE = ZoneInfo("Asia/Shanghai")
SESSION_ID = "qveris-social-studio-top-gainers"
QVERIS_TOP_GAINERS_TOOL_ID = os.environ.get("QVERIS_TOP_GAINERS_TOOL_ID", "")
MIN_PRICE = float(os.environ.get("MIN_STOCK_PRICE", "5"))
FALLBACK_MIN_PRICE = float(os.environ.get("FALLBACK_MIN_STOCK_PRICE", "1"))
MIN_VOLUME = int(os.environ.get("MIN_STOCK_VOLUME", "500000"))


def is_common_stock(symbol: str) -> bool:
    special_markers = ("+", "/", "^")
    special_suffixes = ("WS", "WT", "W", "R", "U")
    return not (
        any(marker in symbol for marker in special_markers)
        or symbol.endswith(special_suffixes)
    )


def key_norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def value_by_names(item: dict, names: list[str]) -> object:
    normalized = {key_norm(str(key)): val for key, val in item.items()}
    for name in names:
        target = key_norm(name)
        if target in normalized:
            return normalized[target]
    return None


def symbol_from(item: dict) -> str:
    value = value_by_names(item, ["ticker", "symbol", "stockSymbol", "securitySymbol"])
    if value is None:
        return ""
    symbol = str(value).strip().upper()
    return symbol if re.fullmatch(r"[A-Z][A-Z0-9.\\-]{0,9}", symbol) else ""


def parse_candidate(item: dict) -> dict | None:
    symbol = symbol_from(item)
    if not symbol:
        return None
    price = as_float(
        value_by_names(
            item,
            ["price", "lastPrice", "latestPrice", "currentPrice", "regularMarketPrice", "close"],
        )
    )
    change_amount = as_float(
        value_by_names(
            item,
            ["change", "changeAmount", "regularMarketChange", "netChange"],
        )
    )
    change_pct = as_float(
        value_by_names(
            item,
            [
                "changePercent",
                "changePercentage",
                "changesPercentage",
                "percentChange",
                "regularMarketChangePercent",
            ],
        )
    )
    volume = int(
        as_float(
            value_by_names(
                item,
                ["volume", "regularMarketVolume", "tradingVolume"],
            )
        )
    )
    if not price or not change_pct:
        return None
    return {
        "symbol": symbol,
        "price": price,
        "change_amount": change_amount,
        "change_pct": change_pct,
        "volume": volume,
    }


def parse_stocks(payload: dict) -> list[dict]:
    candidates = []
    seen = set()

    for collection in walk_lists(payload):
        if not collection or not all(isinstance(item, dict) for item in collection[: min(3, len(collection))]):
            continue
        parsed = [parse_candidate(item) for item in collection if isinstance(item, dict)]
        parsed = [item for item in parsed if item]
        if len(parsed) >= 3:
            candidates.extend(parsed)

    if not candidates:
        for item in walk_dicts(payload):
            parsed = parse_candidate(item)
            if parsed:
                candidates.append(parsed)

    unique = []
    for stock in sorted(candidates, key=lambda row: row["change_pct"], reverse=True):
        if stock["symbol"] in seen:
            continue
        seen.add(stock["symbol"])
        unique.append(stock)
    if not unique:
        raise RuntimeError(f"Could not parse stock gainers from QVeris result: {payload}")
    return unique


def fetch_top_gainers() -> dict:
    query = (
        "Top US stock market gainers today by percentage change with ticker, "
        "latest price, change amount, change percentage, and volume"
    )
    return execute_best_tool(
        query,
        SESSION_ID,
        {
            "query": "US stock market top gainers today",
            "market": "US",
            "limit": 25,
        },
        configured_tool_id=QVERIS_TOP_GAINERS_TOOL_ID,
        max_response_size=65536,
    )


def filter_stocks(stocks: list[dict], min_price: float, min_volume: int) -> list[dict]:
    return [
        stock
        for stock in stocks
        if stock["price"] >= min_price
        and stock["volume"] >= min_volume
        and is_common_stock(stock["symbol"])
    ]


def parse_top5(payload: dict) -> tuple[list[dict], dict]:
    stocks = parse_stocks(payload)
    filter_tiers = [
        {
            "label": "primary",
            "min_price": MIN_PRICE,
            "min_volume": MIN_VOLUME,
            "exclude_special_tickers": True,
        },
        {
            "label": "fallback_price",
            "min_price": FALLBACK_MIN_PRICE,
            "min_volume": MIN_VOLUME,
            "exclude_special_tickers": True,
        },
    ]

    for filters in filter_tiers:
        filtered = filter_stocks(stocks, filters["min_price"], filters["min_volume"])
        if len(filtered) >= 5:
            filters["matched_count"] = len(filtered)
            return filtered[:5], filters

    relaxed = [
        stock
        for stock in stocks
        if stock["price"] >= FALLBACK_MIN_PRICE and is_common_stock(stock["symbol"])
    ]
    if len(relaxed) >= 5:
        return relaxed[:5], {
            "label": "relaxed_volume",
            "min_price": FALLBACK_MIN_PRICE,
            "min_volume": 0,
            "exclude_special_tickers": True,
            "matched_count": len(relaxed),
        }

    raw_fill = stocks[:5]
    if len(raw_fill) < 5:
        raise RuntimeError(
            f"QVeris returned only {len(raw_fill)} usable gainers after parsing."
        )
    return raw_fill, {
        "label": "raw_fill",
        "min_price": 0,
        "min_volume": 0,
        "exclude_special_tickers": False,
        "matched_count": len(raw_fill),
        "warning": "Strict filters produced fewer than 5 stocks; raw QVeris gainers were used to keep the daily archive running.",
    }


def main() -> dict:
    raw = fetch_top_gainers()
    now = datetime.now(timezone.utc)
    run_now = datetime.now(RUN_TIMEZONE)
    top5, filters = parse_top5(raw)
    output = {
        "updated_at": now.isoformat(),
        "date": run_now.strftime("%Y-%m-%d"),
        "run_timezone": "Asia/Shanghai",
        "market_date": run_now.strftime("%Y-%m-%d"),
        "last_updated_label": run_now.strftime("%Y-%m-%d %H:%M %Z"),
        "source": "QVeris API",
        "filters": filters,
        "top5": top5,
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Saved {OUTPUT_FILE}")
    for rank, stock in enumerate(output["top5"], 1):
        print(
            f"  #{rank} {stock['symbol']} "
            f"{stock['change_pct']:+.2f}% ${stock['price']:.2f}"
        )

    return output


if __name__ == "__main__":
    main()
