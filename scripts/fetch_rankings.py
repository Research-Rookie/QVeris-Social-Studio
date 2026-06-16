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


def parse_top5(data: dict) -> list[dict]:
    return [
        {
            "symbol": item["ticker"],
            "price": float(item["price"]),
            "change_amount": float(item["change_amount"]),
            "change_pct": float(item["change_percentage"].rstrip("%")),
            "volume": int(item["volume"]),
        }
        for item in data["top_gainers"][:5]
    ]


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
    output = {
        "updated_at": now.isoformat(),
        "date": run_now.strftime("%Y-%m-%d"),
        "run_timezone": "Asia/Shanghai",
        "market_date": source_market_date,
        "last_updated_label": last_updated,
        "top5": parse_top5(raw),
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
