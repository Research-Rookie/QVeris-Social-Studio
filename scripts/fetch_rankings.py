"""Fetch the daily Top 5 U.S. stock gainers from Alpha Vantage."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests


API_URL = "https://www.alphavantage.co/query"
ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_FILE = ROOT_DIR / "data" / "rankings.json"
RUN_TIMEZONE = ZoneInfo("Asia/Shanghai")
MIN_PRICE = float(os.environ.get("MIN_STOCK_PRICE", "5"))
FALLBACK_MIN_PRICE = float(os.environ.get("FALLBACK_MIN_STOCK_PRICE", "1"))
MIN_VOLUME = int(os.environ.get("MIN_STOCK_VOLUME", "500000"))


def fetch_top_gainers(api_key: str) -> dict:
    response = requests.get(
        API_URL,
        params={"function": "TOP_GAINERS_LOSERS", "apikey": api_key},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()

    if "top_gainers" not in data:
        raise RuntimeError(f"Unexpected Alpha Vantage response: {data}")

    return data


def is_common_stock(symbol: str) -> bool:
    special_markers = ("+", "/", "^")
    special_suffixes = ("WS", "WT", "W", "R", "U")
    return not (
        any(marker in symbol for marker in special_markers)
        or symbol.endswith(special_suffixes)
    )


def parse_stock(item: dict) -> dict:
    return {
        "symbol": item["ticker"],
        "price": float(item["price"]),
        "change_amount": float(item["change_amount"]),
        "change_pct": float(item["change_percentage"].rstrip("%")),
        "volume": int(item["volume"]),
    }


def filter_stocks(stocks: list[dict], min_price: float, min_volume: int) -> list[dict]:
    filtered = []
    for stock in stocks:
        if (
            stock["price"] >= min_price
            and stock["volume"] >= min_volume
            and is_common_stock(stock["symbol"])
        ):
            filtered.append(stock)

    return filtered


def unique_stocks(stocks: list[dict]) -> list[dict]:
    seen = set()
    unique = []
    for stock in stocks:
        if stock["symbol"] in seen:
            continue
        seen.add(stock["symbol"])
        unique.append(stock)
    return unique


def parse_top5(data: dict) -> tuple[list[dict], dict]:
    stocks = [parse_stock(item) for item in data["top_gainers"]]
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
        filtered = filter_stocks(
            stocks,
            min_price=filters["min_price"],
            min_volume=filters["min_volume"],
        )
        if len(filtered) >= 5:
            filters["matched_count"] = len(filtered)
            return filtered[:5], filters

    relaxed_common = [
        stock
        for stock in stocks
        if stock["price"] >= FALLBACK_MIN_PRICE and is_common_stock(stock["symbol"])
    ]
    combined = unique_stocks(filtered + relaxed_common)
    if len(combined) >= 5:
        return combined[:5], {
            "label": "relaxed_volume",
            "min_price": FALLBACK_MIN_PRICE,
            "min_volume": 0,
            "exclude_special_tickers": True,
            "matched_count": len(combined),
        }

    raw_fill = unique_stocks(combined + stocks)
    if len(raw_fill) < 5:
        raise RuntimeError(
            f"Alpha Vantage returned only {len(raw_fill)} usable gainers."
        )

    return raw_fill[:5], {
        "label": "raw_fill",
        "min_price": 0,
        "min_volume": 0,
        "exclude_special_tickers": False,
        "matched_count": len(raw_fill),
        "warning": "Strict filters produced fewer than 5 stocks; raw gainers were used to keep the daily archive running.",
    }


def market_date(last_updated: str, fallback: datetime) -> str:
    candidate = last_updated[:10]
    try:
        datetime.strptime(candidate, "%Y-%m-%d")
        return candidate
    except ValueError:
        return fallback.strftime("%Y-%m-%d")


def main() -> dict:
    api_key = os.environ.get("ALPHA_VANTAGE_API_KEY")
    if not api_key:
        raise RuntimeError("ALPHA_VANTAGE_API_KEY is not set")

    raw = fetch_top_gainers(api_key)
    now = datetime.now(timezone.utc)
    run_now = datetime.now(RUN_TIMEZONE)
    last_updated = raw.get("last_updated", "")
    source_market_date = market_date(last_updated, now)
    top5, filters = parse_top5(raw)
    output = {
        "updated_at": now.isoformat(),
        "date": run_now.strftime("%Y-%m-%d"),
        "run_timezone": "Asia/Shanghai",
        "market_date": source_market_date,
        "last_updated_label": last_updated,
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
