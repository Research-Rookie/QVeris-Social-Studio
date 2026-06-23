"""Fetch World Cup finance signal data from FMP quote-short."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


FMP_API_URL = "https://financialmodelingprep.com/stable"
QVERIS_BASE_URL = os.environ.get("QVERIS_API_BASE_URL", "https://qveris.ai/api/v1")
QVERIS_API_KEY = os.environ.get("QVERIS_API_KEY")
QVERIS_SESSION_ID = "qveris-social-studio-world-cup-finance"
QVERIS_STOCK_QUOTE_TOOL_ID = os.environ.get("QVERIS_STOCK_QUOTE_TOOL_ID", "")
QVERIS_STOCK_QUOTE_PARAM = os.environ.get("QVERIS_STOCK_QUOTE_PARAM", "")
QVERIS_MAX_EXPECTED_CREDITS = float(os.environ.get("QVERIS_MAX_EXPECTED_CREDITS", "10"))
ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = ROOT_DIR / "data" / "world_cup_finance_config.json"
OUTPUT_FILE = ROOT_DIR / "data" / "world_cup_finance.json"
RUN_TIMEZONE = ZoneInfo("Asia/Shanghai")
QVERIS_TOOL_CACHE: dict[str, str] = {}


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


def qveris_headers() -> dict[str, str]:
    if not QVERIS_API_KEY:
        raise RuntimeError("QVERIS_API_KEY is not set")
    return {
        "Authorization": f"Bearer {QVERIS_API_KEY}",
        "Content-Type": "application/json",
    }


def qveris_post(path: str, payload: dict, query: dict | None = None) -> dict:
    body = json.dumps(payload).encode("utf-8")
    suffix = f"?{urlencode(query)}" if query else ""
    request = Request(
        f"{QVERIS_BASE_URL}{path}{suffix}",
        data=body,
        headers=qveris_headers(),
        method="POST",
    )
    try:
        with urlopen(request, timeout=45) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"QVeris API error {error.code} for {path}: {details}") from error


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


def expected_credits(tool: dict) -> float:
    billing_rule = tool.get("billing_rule") or {}
    price = billing_rule.get("price") or {}
    candidates = [
        billing_rule.get("amount_credits"),
        billing_rule.get("amount"),
        price.get("amount_credits") if isinstance(price, dict) else None,
        tool.get("cost"),
    ]
    for candidate in candidates:
        if candidate not in (None, ""):
            try:
                return float(candidate)
            except (TypeError, ValueError):
                pass

    text = str(tool.get("expected_cost") or "")
    numbers = []
    for token in text.replace(",", " ").split():
        try:
            numbers.append(float(token))
        except ValueError:
            pass
    return numbers[0] if numbers else 0.0


def choose_symbol_param(tool: dict) -> str | None:
    preferred = ["symbol", "ticker", "stock_symbol", "stock", "query"]
    params = tool.get("params") or []
    names = [str(param.get("name", "")) for param in params]
    lowered = {name.lower(): name for name in names}
    for name in preferred:
        if name in lowered:
            return lowered[name]
    return names[0] if len(names) == 1 else None


def discover_qveris_stock_quote_tool() -> tuple[str, str, str]:
    if QVERIS_STOCK_QUOTE_TOOL_ID:
        return (
            QVERIS_STOCK_QUOTE_TOOL_ID,
            QVERIS_STOCK_QUOTE_PARAM or "symbol",
            "configured",
        )

    if "tool_id" in QVERIS_TOOL_CACHE:
        return (
            QVERIS_TOOL_CACHE["tool_id"],
            QVERIS_TOOL_CACHE["param_name"],
            QVERIS_TOOL_CACHE.get("search_id", ""),
        )

    query = (
        "current stock quote by ticker symbol with latest price, daily change, "
        "change percentage, and volume"
    )
    data = qveris_post(
        "/search",
        {
            "query": query,
            "limit": 8,
            "session_id": QVERIS_SESSION_ID,
        },
    )
    results = data.get("results") or []
    search_id = data.get("search_id") or ""
    candidates = []
    for result in results:
        param_name = choose_symbol_param(result)
        if not param_name:
            continue
        cost = expected_credits(result)
        if cost and cost > QVERIS_MAX_EXPECTED_CREDITS:
            continue
        candidates.append((cost, result, param_name))

    if not candidates:
        raise RuntimeError("No low-cost QVeris stock quote capability found")

    candidates.sort(key=lambda item: item[0])
    _, selected, param_name = candidates[0]
    QVERIS_TOOL_CACHE.update(
        {
            "tool_id": selected["tool_id"],
            "param_name": param_name,
            "search_id": search_id,
        }
    )
    print(
        "QVeris stock quote tool: "
        f"{selected.get('name')} ({selected['tool_id']}, param={param_name})"
    )
    return selected["tool_id"], param_name, search_id


def walk_values(value: object) -> list[dict]:
    dicts = []
    if isinstance(value, dict):
        dicts.append(value)
        for child in value.values():
            dicts.extend(walk_values(child))
    elif isinstance(value, list):
        for child in value:
            dicts.extend(walk_values(child))
    return dicts


def normalized_key(key: str) -> str:
    return "".join(char for char in key.lower() if char.isalnum())


def find_numeric(payload: dict, names: list[str]) -> float:
    targets = [normalized_key(name) for name in names]
    for item in walk_values(payload):
        normalized = {normalized_key(str(key)): value for key, value in item.items()}
        for target in targets:
            if target in normalized:
                try:
                    return as_float(normalized[target])
                except (TypeError, ValueError):
                    continue
    return 0.0


def fetch_qveris_quote(symbol: str) -> dict | None:
    if not QVERIS_API_KEY:
        return None

    tool_id, param_name, search_id = discover_qveris_stock_quote_tool()
    data = qveris_post(
        "/tools/execute",
        {
            "search_id": search_id,
            "session_id": QVERIS_SESSION_ID,
            "parameters": {param_name: symbol},
            "max_response_size": 20480,
        },
        {"tool_id": tool_id},
    )
    if not data.get("success", False):
        raise RuntimeError(data.get("error_message") or f"QVeris execution failed for {symbol}")

    result = data.get("result") or {}
    price = find_numeric(result, ["price", "latestPrice", "regularMarketPrice", "05. price"])
    change = find_numeric(result, ["change", "regularMarketChange", "09. change"])
    change_pct = find_numeric(
        result,
        [
            "changePercent",
            "changesPercentage",
            "regularMarketChangePercent",
            "10. change percent",
            "change_percentage",
        ],
    )
    volume = int(find_numeric(result, ["volume", "regularMarketVolume", "06. volume"]))
    if not price:
        raise RuntimeError(f"QVeris result did not include a price for {symbol}")
    if not change_pct and price and change:
        previous = price - change
        change_pct = change / previous * 100 if previous else 0

    return {
        "symbol": symbol,
        "price": price,
        "change": change,
        "change_pct": change_pct,
        "market_cap": find_numeric(result, ["marketCap", "market_cap"]),
        "volume": volume,
    }


def fetch_quote(symbol: str, api_key: str | None) -> dict | None:
    try:
        qveris_quote = fetch_qveris_quote(symbol)
        if qveris_quote:
            qveris_quote["source"] = "QVeris API"
            return qveris_quote
    except RuntimeError as error:
        print(f"Warning: QVeris quote unavailable for {symbol}: {error}")

    if not api_key:
        print(f"Warning: no FMP fallback key set for {symbol}")
        return None

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
    if not api_key and not QVERIS_API_KEY:
        raise RuntimeError("Set QVERIS_API_KEY or FMP_API_KEY")

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

    sources = sorted({stock.get("source", "FMP quote-short") for stock in stocks})
    output = {
        "updated_at": now.isoformat(),
        "date": run_now.strftime("%Y-%m-%d"),
        "run_timezone": "Asia/Shanghai",
        "source": ", ".join(sources),
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
