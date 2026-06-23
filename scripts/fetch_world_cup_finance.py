"""Fetch World Cup finance signal data from FMP quote-short."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen
from zoneinfo import ZoneInfo


FMP_API_URL = "https://financialmodelingprep.com/stable"
ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = ROOT_DIR / "data" / "world_cup_finance_config.json"
OUTPUT_FILE = ROOT_DIR / "data" / "world_cup_finance.json"
RUN_TIMEZONE = ZoneInfo("Asia/Shanghai")


def fmp_get(path: str, api_key: str, params: dict) -> list | dict:
    query = {"apikey": api_key}
    query.update(params)
    url = f"{FMP_API_URL}/{path}?{urlencode(query)}"
    try:
        with urlopen(url, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"FMP API error {error.code} for {path}: {details}") from error


def as_float(value: object) -> float:
    if value is None or value == "":
        return 0.0
    if isinstance(value, str):
        value = value.replace("%", "")
    return float(value)


def parse_quote(raw: dict, fallback_symbol: str) -> dict:
    symbol = str(raw.get("symbol") or fallback_symbol).upper()
    price = as_float(raw.get("price"))
    change = as_float(raw.get("change"))
    previous = price - change
    change_pct = change / previous * 100 if previous else 0
    return {
        "symbol": symbol,
        "price": price,
        "change": change,
        "change_pct": change_pct,
        "market_cap": 0,
        "volume": int(as_float(raw.get("volume"))),
    }


def fetch_quote(symbol: str, api_key: str) -> dict | None:
    try:
        data = fmp_get("quote-short", api_key, {"symbol": symbol})
    except RuntimeError as error:
        print(f"Warning: quote unavailable for {symbol}: {error}")
        return None
    if not isinstance(data, list) or not data:
        print(f"Warning: no quote returned for {symbol}")
        return None
    return parse_quote(data[0], symbol)


def format_match(match: dict | None) -> str:
    if not match:
        return "Match result pending"
    home = match.get("home_team") or "TBD"
    away = match.get("away_team") or "TBD"
    home_score = match.get("home_score")
    away_score = match.get("away_score")
    if home_score is None or away_score is None:
        return str(match.get("label") or "Match result pending")
    return f"{home} {home_score}-{away_score} {away}"


def top_theme(stocks: list[dict]) -> tuple[str, float]:
    theme_moves: dict[str, list[float]] = {}
    for stock in stocks:
        theme_moves.setdefault(stock["theme"], []).append(stock["change_pct"])
    averages = {
        theme: sum(values) / len(values)
        for theme, values in theme_moves.items()
        if values
    }
    if not averages:
        return "Sponsor basket", 0.0
    theme, value = max(averages.items(), key=lambda item: item[1])
    return theme, value


def main() -> dict:
    api_key = os.environ.get("FMP_API_KEY")
    if not api_key:
        raise RuntimeError("FMP_API_KEY is not set")

    config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc)
    run_now = datetime.now(RUN_TIMEZONE)
    stocks = []

    for item in config["basket"]:
        quote = fetch_quote(item["symbol"], api_key)
        if not quote:
            continue
        stocks.append(
            {
                **quote,
                "company": item["company"],
                "theme": item["theme"],
            }
        )

    if len(stocks) < 5:
        raise RuntimeError(f"Only fetched {len(stocks)} World Cup finance stocks")

    stocks.sort(key=lambda stock: stock["change_pct"], reverse=True)
    leader = stocks[0]
    theme, theme_change = top_theme(stocks)

    output = {
        "updated_at": now.isoformat(),
        "date": run_now.strftime("%Y-%m-%d"),
        "run_timezone": "Asia/Shanghai",
        "source": "Financial Modeling Prep quote-short",
        "event": config.get("event", "2026 FIFA World Cup"),
        "latest_match": config.get("latest_match"),
        "match_label": format_match(config.get("latest_match")),
        "leader": leader,
        "top_theme": {
            "name": theme,
            "avg_change_pct": theme_change,
        },
        "stocks": stocks,
    }

    OUTPUT_FILE.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Saved {OUTPUT_FILE}")
    print(f"Match: {output['match_label']}")
    print(f"Leader: ${leader['symbol']} {leader['change_pct']:+.2f}%")
    print(f"Top theme: {theme} {theme_change:+.2f}%")
    return output


if __name__ == "__main__":
    main()
import os
