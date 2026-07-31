"""Run the same finance question through multiple QVeris-discovered APIs."""

from __future__ import annotations

import json
import math
import os
import re
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import urlopen
from zoneinfo import ZoneInfo

from qveris_finance import (
    expected_credits,
    execute_tool,
    fill_default_parameters,
    search_tools,
    walk_dicts,
)


ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_FILE = ROOT_DIR / "data" / "live_api_battle.json"
RUN_TIMEZONE = ZoneInfo("Asia/Shanghai")
SESSION_ID = "qveris-social-studio-live-api-battle"
MAX_CANDIDATES = int(os.environ.get("LIVE_API_BATTLE_MAX_CANDIDATES", "10"))

SYMBOLS = [
    {"symbol": "AAPL", "company": "Apple"},
    {"symbol": "NVDA", "company": "NVIDIA"},
    {"symbol": "MSFT", "company": "Microsoft"},
    {"symbol": "AMZN", "company": "Amazon"},
    {"symbol": "GOOGL", "company": "Alphabet"},
]

FIELD_ALIASES = {
    "symbol": ["symbol", "ticker", "code"],
    "price": [
        "price",
        "last",
        "lastTradePrice",
        "lastPrice",
        "latestPrice",
        "currentPrice",
        "regularMarketPrice",
        "close",
        "05. price",
        "c",
    ],
    "change_pct": [
        "changePercent",
        "changePercentage",
        "changesPercentage",
        "percentChange",
        "regularMarketChangePercent",
        "10. change percent",
        "change_p",
        "dp",
    ],
    "volume": ["volume", "regularMarketVolume", "tradingVolume", "06. volume"],
    "as_of": [
        "timestamp",
        "datetime",
        "lastUpdated",
        "lastUpdate",
        "updatedAt",
        "latestTradingDay",
        "07. latest trading day",
        "date",
        "t",
    ],
}


def key_norm(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def as_number(value: Any) -> float | None:
    if value in (None, "", "N/A", "n/a", "-"):
        return None
    if isinstance(value, bool):
        return None
    multiplier = 1.0
    if isinstance(value, str):
        cleaned = value.strip().replace(",", "").replace("$", "").replace("%", "")
        if cleaned and cleaned[-1].upper() in {"K", "M", "B", "T"}:
            multiplier = {
                "K": 1_000,
                "M": 1_000_000,
                "B": 1_000_000_000,
                "T": 1_000_000_000_000,
            }[cleaned[-1].upper()]
            cleaned = cleaned[:-1]
        value = cleaned
    try:
        parsed = float(value) * multiplier
        return parsed if math.isfinite(parsed) else None
    except (TypeError, ValueError):
        return None


def value_by_aliases(item: dict[str, Any], aliases: list[str]) -> Any:
    normalized = {key_norm(key): value for key, value in item.items()}
    for alias in aliases:
        if key_norm(alias) in normalized:
            return normalized[key_norm(alias)]
    return None


def parse_embedded_payload(payload: Any) -> Any:
    if isinstance(payload, str) and payload.strip().startswith(("[", "{")):
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return payload
    if not isinstance(payload, dict):
        return payload
    full_content_url = payload.get("full_content_file_url")
    if isinstance(full_content_url, str) and full_content_url.startswith(("http://", "https://")):
        try:
            with urlopen(full_content_url, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as error:
            print(f"Full response download warning: {error}")
    content = payload.get("truncated_content") or payload.get("content") or payload.get("data")
    if isinstance(content, str) and content.strip().startswith(("[", "{")):
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
    return payload


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
        "marketstack": "Marketstack",
        "tiingo": "Tiingo",
        "tradier": "Tradier",
    }
    for namespace, label in namespaces.items():
        if tool_id.startswith(namespace):
            return label
    return "Provider not stated"


def capability_label(tool: dict[str, Any]) -> str:
    name = str(tool.get("name") or tool.get("capability") or "").strip()
    tool_id = str(tool.get("tool_id") or "").lower()
    generic_names = {"symbol", "ticker", "s", "code", "query"}
    if name and name.lower() not in generic_names:
        return name
    labels = {
        "alphavantage.realtime_bulk_quotes": "Realtime Bulk Quotes",
        "finnhub_io_api.stock.quote": "Stock Quote",
        "finnhub.quote": "Stock Quote",
        "tiingo.core.eod": "End-of-Day Quote",
        "eodhd.live_v2.us_quote": "Delayed U.S. Quote",
    }
    for prefix, label in labels.items():
        if tool_id.startswith(prefix):
            return label
    return name or "Quote capability"


def parse_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        timestamp = float(value)
        if timestamp > 10_000_000_000:
            timestamp /= 1000
        try:
            return datetime.fromtimestamp(timestamp, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    text = str(value).strip()
    if not text:
        return None
    candidates = [text, text.replace("Z", "+00:00")]
    for candidate in candidates:
        try:
            parsed = datetime.fromisoformat(candidate)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            pass
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(text[:10], fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return None


def quote_candidates(payload: Any, symbol: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for item in walk_dicts(payload):
        item_symbol = str(value_by_aliases(item, FIELD_ALIASES["symbol"]) or "").replace("$", "").upper()
        if item_symbol and item_symbol != symbol:
            continue
        price = as_number(value_by_aliases(item, FIELD_ALIASES["price"]))
        change_pct = as_number(value_by_aliases(item, FIELD_ALIASES["change_pct"]))
        volume = as_number(value_by_aliases(item, FIELD_ALIASES["volume"]))
        as_of_raw = value_by_aliases(item, FIELD_ALIASES["as_of"])
        if any(value is not None for value in (price, change_pct, volume)):
            candidates.append(
                {
                    "symbol": item_symbol or symbol,
                    "price": price,
                    "change_pct": change_pct,
                    "volume": volume,
                    "as_of_raw": str(as_of_raw or ""),
                    "as_of": parse_datetime(as_of_raw),
                }
            )
    return candidates


def parse_quote(payload: Any, symbol: str) -> dict[str, Any]:
    parsed = parse_embedded_payload(payload)
    candidates = quote_candidates(parsed, symbol)
    if not candidates:
        return {
            "symbol": symbol,
            "price": None,
            "change_pct": None,
            "volume": None,
            "as_of": None,
            "as_of_raw": "",
            "completeness": 0.0,
        }
    candidates.sort(
        key=lambda item: sum(item.get(field) is not None for field in ("price", "change_pct", "volume", "as_of")),
        reverse=True,
    )
    quote = candidates[0]
    quote["completeness"] = sum(quote.get(field) is not None for field in ("price", "change_pct", "volume")) / 3
    return quote


def freshness_details(as_of: datetime | None, raw: str, now: datetime) -> tuple[str, float]:
    if as_of is None:
        return ("Time returned" if raw else "Time n/a", 0.35 if raw else 0.15)
    age_hours = max((now - as_of).total_seconds() / 3600, 0)
    day_gap = (now.date() - as_of.date()).days
    if day_gap <= 0:
        return "Today", 1.0
    if day_gap == 1:
        return "Previous session", 0.88
    if age_hours <= 72:
        return f"{max(1, round(age_hours / 24))}d old", 0.75
    return as_of.strftime("%b %d"), 0.45


def cost_details(tool: dict[str, Any]) -> tuple[float | None, str]:
    known = any(tool.get(key) not in (None, "", {}) for key in ("expected_cost", "cost", "billing_rule"))
    if not known:
        return None, "Cost n/a"
    cost = expected_credits(tool)
    if cost == 0:
        return 0.0, "Free"
    return cost, f"{cost:g} cr"


def run_candidate(tool: dict[str, Any], search_id: str, symbol: str, now: datetime) -> dict[str, Any]:
    name = capability_label(tool)
    provider = provider_label(tool)
    cost, cost_label = cost_details(tool)
    parameters = fill_default_parameters(
        tool,
        {
            "symbol": symbol,
            "ticker": symbol,
            "function": "GLOBAL_QUOTE",
            "market": "US",
            "region": "US",
            "limit": 10,
            "query": symbol,
        },
    )
    for param in tool.get("params") or []:
        param_name = str(param.get("name") or "")
        if key_norm(param_name) in {"s", "code", "stockcode", "instrument"}:
            parameters[param_name] = symbol
    started = time.perf_counter()
    try:
        payload = execute_tool(
            str(tool["tool_id"]),
            SESSION_ID,
            parameters,
            search_id=search_id,
            max_response_size=65536,
        )
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        quote = parse_quote(payload, symbol)
        freshness_label, freshness_score = freshness_details(quote.get("as_of"), quote.get("as_of_raw", ""), now)
        return {
            "tool_id": str(tool.get("tool_id") or ""),
            "name": name,
            "provider": provider,
            "success": True,
            "latency_ms": elapsed_ms,
            "cost_credits": cost,
            "cost_label": cost_label,
            "price": quote.get("price"),
            "change_pct": quote.get("change_pct"),
            "volume": quote.get("volume"),
            "as_of": quote.get("as_of").isoformat() if quote.get("as_of") else quote.get("as_of_raw", ""),
            "freshness_label": freshness_label,
            "freshness_score": freshness_score,
            "completeness": quote.get("completeness", 0.0),
            "error": "" if quote.get("completeness", 0) else "Call succeeded; quote fields were not parsed",
        }
    except Exception as error:
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        return {
            "tool_id": str(tool.get("tool_id") or ""),
            "name": name,
            "provider": provider,
            "success": False,
            "latency_ms": elapsed_ms,
            "cost_credits": cost,
            "cost_label": cost_label,
            "price": None,
            "change_pct": None,
            "volume": None,
            "as_of": "",
            "freshness_label": "Failed",
            "freshness_score": 0.0,
            "completeness": 0.0,
            "error": " ".join(str(error).split())[:180],
        }


def unique_candidates(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen_providers: set[str] = set()
    for result in results:
        if not result.get("tool_id"):
            continue
        searchable = " ".join(
            str(result.get(key) or "")
            for key in ("name", "description", "tool_id")
        ).lower()
        excluded = (
            "clock",
            "calendar",
            "exchange status",
            "orderbook",
            "order book",
            "trades list",
            "cryptocurrency",
            "crypto",
            "coinmarketcap",
            "coingecko",
            "binance",
            "forex",
        )
        quote_signal = any(
            token in searchable
            for token in ("quote", "stock price", "real-time", "realtime", "live price", ".eod.", "global_quote")
        )
        param_names = {key_norm(param.get("name")) for param in result.get("params") or []}
        accepts_symbol = bool(param_names & {"symbol", "ticker", "s", "code", "stock", "stockcode"})
        if any(token in searchable for token in excluded) or not quote_signal or not accepts_symbol:
            continue
        provider = provider_label(result)
        provider_key = provider.lower()
        if provider != "Provider not stated" and provider_key in seen_providers:
            continue
        seen_providers.add(provider_key)
        selected.append(result)
        if len(selected) >= MAX_CANDIDATES:
            break
    return selected


def score_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    parsed_prices = [float(item["price"]) for item in results if item.get("price") not in (None, 0)]
    median_price = statistics.median(parsed_prices) if parsed_prices else None
    successful_latency = [float(item["latency_ms"]) for item in results if item.get("success")]
    fastest = min(successful_latency) if successful_latency else 1.0
    known_costs = [float(item["cost_credits"]) for item in results if item.get("cost_credits") is not None]
    cheapest = min(known_costs) if known_costs else 0.0

    for item in results:
        if not item.get("success"):
            item["agreement_score"] = 0.0
            item["battle_score"] = 0.0
            continue
        price = item.get("price")
        if median_price and price:
            deviation = abs(float(price) - median_price) / median_price
            agreement = max(0.0, 1 - deviation / 0.03)
        else:
            agreement = 0.35
        latency_score = min(1.0, fastest / max(float(item["latency_ms"]), 1))
        if item.get("cost_credits") is None:
            cost_score = 0.35
        else:
            cost_score = 1 / (1 + max(float(item["cost_credits"]) - cheapest, 0) / 5)
        score = (
            float(item.get("completeness") or 0) * 0.40
            + latency_score * 0.25
            + float(item.get("freshness_score") or 0) * 0.15
            + cost_score * 0.10
            + agreement * 0.10
        ) * 100
        item["agreement_score"] = round(agreement, 3)
        item["battle_score"] = round(score, 1)

    results.sort(
        key=lambda item: (
            bool(item.get("success")),
            float(item.get("battle_score") or 0),
            float(item.get("completeness") or 0),
        ),
        reverse=True,
    )
    for rank, item in enumerate(results, start=1):
        item["rank"] = rank
    return results


def main() -> dict[str, Any]:
    run_now = datetime.now(RUN_TIMEZONE)
    now_utc = datetime.now(timezone.utc)
    scenario = SYMBOLS[run_now.date().toordinal() % len(SYMBOLS)]
    symbol = scenario["symbol"]
    question = f"What is {symbol}'s latest U.S. stock quote?"
    query = (
        f"API endpoint to retrieve the latest U.S. stock quote for ticker {symbol}, including "
        "current price, percent change, trading volume, and timestamp; exclude market clock, "
        "calendar, exchange status, order book, and news tools"
    )
    search_id, discovered = search_tools(query, SESSION_ID, limit=20)
    candidates = unique_candidates(discovered)
    if len(candidates) < 2:
        raise RuntimeError(f"QVeris Discover returned fewer than two distinct API candidates: {len(candidates)}")

    attempted: list[dict[str, Any]] = []
    for candidate in candidates:
        print(
            f"Trying {candidate.get('name')} ({candidate.get('tool_id')}); "
            f"params={[param.get('name') for param in candidate.get('params') or []]}"
        )
        result = run_candidate(candidate, search_id, symbol, now_utc)
        attempted.append(result)
        print(
            f"{result['provider']}: {'ok' if result['success'] else 'failed'}, "
            f"{result['latency_ms']}ms, completeness={result['completeness']:.0%}"
        )
        usable = [item for item in attempted if item.get("success") and item.get("completeness", 0) > 0]
        if len(usable) >= 3:
            break

    usable = [item for item in attempted if item.get("success") and item.get("completeness", 0) > 0]
    failures = [item for item in attempted if item not in usable]
    participants = (usable[:3] + failures[: max(0, 3 - len(usable))])[:3]
    if len(usable) < 2:
        raise RuntimeError(
            f"Only {len(usable)} QVeris-discovered API returned parseable quote data; "
            "at least two are required for a real comparison"
        )
    participants = score_results(participants)
    winner = participants[0]
    winner_reason = (
        f"{winner['provider']} returned {winner['completeness']:.0%} of the requested quote fields "
        f"in {winner['latency_ms']:,}ms."
    )
    prices = [float(item["price"]) for item in participants if item.get("price") not in (None, 0)]
    price_spread_pct = ((max(prices) - min(prices)) / statistics.median(prices) * 100) if len(prices) >= 2 else None

    output = {
        "updated_at": now_utc.isoformat(),
        "date": run_now.strftime("%Y-%m-%d"),
        "run_timezone": "Asia/Shanghai",
        "source": "Live calls through QVeris API",
        "title": "Live API Battle",
        "question": question,
        "scenario": scenario,
        "search_id": search_id,
        "discovered_count": len(discovered),
        "attempted_count": len(attempted),
        "participants": participants,
        "winner": winner,
        "winner_reason": winner_reason,
        "price_spread_pct": round(price_spread_pct, 3) if price_spread_pct is not None else None,
        "methodology": {
            "completeness_weight": 0.40,
            "live_latency_weight": 0.25,
            "freshness_weight": 0.15,
            "expected_cost_weight": 0.10,
            "price_agreement_weight": 0.10,
            "note": (
                "Latency is measured end to end during this run. Cost is the expected QVeris "
                "Discover signal. A higher score means a better response for this task, not universal accuracy."
            ),
        },
    }
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {OUTPUT_FILE}")
    print(f"Winner: {winner['provider']} ({winner['battle_score']:.1f})")
    return output


if __name__ == "__main__":
    main()
