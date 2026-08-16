"""Run ten live, cross-category API Battles for a client-facing report.

The benchmark is independent from the daily Social Studio archive. It writes
one JSON artifact and does not modify posts.json or public website images.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.request import urlopen
from zoneinfo import ZoneInfo

from fetch_live_api_battle import capability_label, provider_label
from qveris_finance import (
    QVERIS_MAX_EXPECTED_CREDITS,
    execute_tool,
    expected_credits,
    fill_default_parameters,
    search_tools,
    walk_dicts,
)


ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT_DIR / "benchmark-results"
RUN_TIMEZONE = ZoneInfo("Asia/Shanghai")
SESSION_ID = "qveris-client-cross-category-api-battle"
MAX_EXECUTIONS = 4
TARGET_USABLE = 3


SCENARIOS: list[dict[str, Any]] = [
    {
        "key": "stock-quote",
        "label": "Real-time stock quote",
        "entity": "AAPL",
        "prompt": "What is AAPL's latest stock price, daily percentage change, trading volume, and quote timestamp?",
        "query": "latest US stock quote API price percent change volume timestamp for AAPL",
        "fields": {
            "price": ["price", "latestPrice", "currentPrice", "regularMarketPrice", "05. price", "c"],
            "change_pct": ["changePercent", "changesPercentage", "percentChange", "10. change percent", "dp"],
            "volume": ["volume", "regularMarketVolume", "tradingVolume", "06. volume"],
            "timestamp": ["timestamp", "datetime", "latestTradingDay", "07. latest trading day", "date", "t"],
        },
        "params": {"symbol": "AAPL", "ticker": "AAPL", "query": "AAPL", "function": "GLOBAL_QUOTE"},
    },
    {
        "key": "earnings",
        "label": "Company earnings",
        "entity": "NVDA",
        "prompt": "What were NVIDIA's latest reported EPS, estimated EPS, earnings surprise percentage, revenue, and reporting date?",
        "query": "company earnings API reported EPS estimated EPS surprise percentage revenue reporting date NVDA",
        "fields": {
            "actual_eps": ["actualEPS", "epsActual", "reportedEPS", "actual", "eps"],
            "estimated_eps": ["estimatedEPS", "epsEstimate", "estimate", "consensusEPS"],
            "surprise_pct": ["surprisePercent", "surprisePercentage", "epsSurprisePercent"],
            "revenue": ["revenue", "actualRevenue", "reportedRevenue"],
            "report_date": ["reportDate", "reportedDate", "fiscalDateEnding", "date", "period"],
        },
        "params": {"symbol": "NVDA", "ticker": "NVDA", "query": "NVIDIA", "function": "EARNINGS", "limit": 5},
    },
    {
        "key": "financial-news",
        "label": "Financial news and sentiment",
        "entity": "TSLA",
        "prompt": "Find the five latest Tesla news articles, including headline, source, publication time, related ticker, and sentiment.",
        "query": "latest company news API headline source publication time ticker sentiment TSLA Tesla",
        "fields": {
            "headline": ["headline", "title", "newsTitle"],
            "source": ["source", "site", "publisher", "sourceName"],
            "published_at": ["publishedAt", "publishedDate", "datetime", "timePublished", "date"],
            "ticker": ["ticker", "symbol", "tickers", "tickerSentiment"],
            "sentiment": ["sentiment", "overallSentimentLabel", "sentimentLabel", "tone"],
        },
        "params": {"symbol": "TSLA", "ticker": "TSLA", "tickers": "TSLA", "query": "Tesla", "limit": 5, "function": "NEWS_SENTIMENT"},
    },
    {
        "key": "sec-filings",
        "label": "SEC filings",
        "entity": "MSFT",
        "prompt": "Find Microsoft's latest 10-K, 10-Q, and 8-K filings, including form type, filing date, accession number, and document URL.",
        "query": "SEC filings API latest 10-K 10-Q 8-K form type filing date accession number document URL MSFT",
        "fields": {
            "form_type": ["formType", "form", "type", "filingType"],
            "filing_date": ["filingDate", "filedAt", "acceptedDate", "date"],
            "accession_number": ["accessionNumber", "accessionNo", "accession_number"],
            "document_url": ["documentUrl", "finalLink", "link", "url", "primaryDocument"],
        },
        "params": {"symbol": "MSFT", "ticker": "MSFT", "cik": "0000789019", "query": "Microsoft", "limit": 20},
    },
    {
        "key": "crypto-market",
        "label": "Crypto market data",
        "entity": "BTC",
        "prompt": "What are Bitcoin's latest price, market capitalization, 24-hour trading volume, 24-hour percentage change, and data timestamp?",
        "query": "cryptocurrency market API Bitcoin latest price market cap 24 hour volume percent change timestamp",
        "fields": {
            "price": ["price", "currentPrice", "last", "close"],
            "market_cap": ["marketCap", "market_cap", "marketCapitalization"],
            "volume_24h": ["volume24h", "totalVolume", "24hVolume", "volume_24h"],
            "change_24h": ["percentChange24h", "priceChangePercentage24h", "change24h"],
            "timestamp": ["lastUpdated", "timestamp", "date", "updatedAt"],
        },
        "params": {"symbol": "BTC", "symbols": "BTC", "id": "bitcoin", "ids": "bitcoin", "query": "Bitcoin", "vs_currency": "usd", "convert": "USD", "limit": 5},
    },
    {
        "key": "us-cpi",
        "label": "U.S. CPI macro data",
        "entity": "US CPI",
        "prompt": "What is the latest U.S. CPI reading, including reporting period, actual value, previous value, release date, and year-over-year change?",
        "query": "US CPI economic data API latest actual previous release date year over year change",
        "fields": {
            "period": ["period", "referencePeriod", "observationDate", "date"],
            "actual_value": ["actual", "value", "cpi", "close"],
            "previous_value": ["previous", "prior", "previousValue"],
            "release_date": ["releaseDate", "publishedAt", "date", "timestamp"],
            "yoy_change": ["yearOverYear", "yoy", "percentChange", "changePercentage"],
        },
        "params": {"series_id": "CPIAUCSL", "series": "CPIAUCSL", "country": "United States", "indicator": "CPI", "query": "US CPI", "limit": 5},
    },
    {
        "key": "forex",
        "label": "FX quote",
        "entity": "EUR/USD",
        "prompt": "What is the latest EUR/USD exchange rate, including bid, ask, daily percentage change, and quote timestamp?",
        "query": "forex API latest EUR USD exchange rate bid ask daily percent change timestamp",
        "fields": {
            "rate": ["exchangeRate", "rate", "price", "close", "last"],
            "bid": ["bid", "bidPrice", "bid_rate"],
            "ask": ["ask", "askPrice", "ask_rate"],
            "change_pct": ["changePercent", "percentChange", "changePercentage"],
            "timestamp": ["timestamp", "datetime", "lastRefreshed", "date"],
        },
        "params": {"symbol": "EURUSD", "pair": "EUR/USD", "from_currency": "EUR", "to_currency": "USD", "base": "EUR", "quote": "USD", "function": "CURRENCY_EXCHANGE_RATE"},
    },
    {
        "key": "options-chain",
        "label": "Options chain",
        "entity": "AAPL options",
        "prompt": "Retrieve Apple's options chain for the nearest expiration date, including strike, option type, bid, ask, implied volatility, volume, and open interest.",
        "query": "stock options chain API nearest expiration strike call put bid ask implied volatility volume open interest AAPL",
        "fields": {
            "expiration": ["expirationDate", "expiration", "expiry", "date"],
            "strike": ["strike", "strikePrice"],
            "option_type": ["optionType", "type", "contractType"],
            "bid": ["bid", "bidPrice"],
            "ask": ["ask", "askPrice"],
            "implied_volatility": ["impliedVolatility", "iv"],
            "volume": ["volume", "totalVolume"],
            "open_interest": ["openInterest", "open_interest"],
        },
        "params": {"symbol": "AAPL", "ticker": "AAPL", "query": "AAPL", "limit": 20},
    },
    {
        "key": "historical-ohlcv",
        "label": "Historical OHLCV",
        "entity": "SPY",
        "prompt": "Retrieve SPY's daily OHLCV data for the latest five trading sessions, including date, open, high, low, close, adjusted close, and volume.",
        "query": "historical daily stock price API OHLCV adjusted close volume latest five sessions SPY",
        "fields": {
            "date": ["date", "datetime", "timestamp"],
            "open": ["open", "1. open"],
            "high": ["high", "2. high"],
            "low": ["low", "3. low"],
            "close": ["close", "4. close"],
            "adjusted_close": ["adjustedClose", "5. adjusted close", "adjClose"],
            "volume": ["volume", "6. volume"],
        },
        "params": {"symbol": "SPY", "ticker": "SPY", "query": "SPY", "interval": "1day", "outputsize": "compact", "function": "TIME_SERIES_DAILY_ADJUSTED", "limit": 5},
    },
    {
        "key": "dividends",
        "label": "Dividend data",
        "entity": "KO",
        "prompt": "What is Coca-Cola's latest dividend information, including amount, ex-dividend date, record date, payment date, frequency, and dividend yield?",
        "query": "company dividend API amount ex-dividend date record date payment date frequency dividend yield KO Coca-Cola",
        "fields": {
            "amount": ["dividend", "dividendAmount", "amount", "cashAmount"],
            "ex_dividend_date": ["exDividendDate", "exDate", "date"],
            "record_date": ["recordDate", "record_date"],
            "payment_date": ["paymentDate", "payDate", "payment_date"],
            "frequency": ["frequency", "dividendFrequency"],
            "dividend_yield": ["dividendYield", "yield"],
        },
        "params": {"symbol": "KO", "ticker": "KO", "query": "Coca-Cola", "limit": 5},
    },
]


def key_norm(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def parse_json_string(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if not stripped.startswith(("{", "[")):
        return value
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return value


def unwrap_payload(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return parse_json_string(payload)
    full_url = payload.get("full_content_file_url")
    if full_url:
        try:
            with urlopen(str(full_url), timeout=45) as response:
                downloaded = response.read().decode("utf-8", errors="replace")
            parsed = parse_json_string(downloaded)
            if isinstance(parsed, (dict, list)):
                return parsed
        except Exception as error:
            print(f"Could not download full response: {error}")
    for name in ("data", "result", "response", "content", "truncated_content"):
        if name in payload and payload[name] not in (None, "", [], {}):
            parsed = parse_json_string(payload[name])
            if isinstance(parsed, (dict, list)):
                return parsed
    return payload


def value_by_aliases(payload: Any, aliases: list[str]) -> Any:
    targets = {key_norm(alias) for alias in aliases}
    for item in walk_dicts(payload):
        for key, value in item.items():
            if key_norm(key) in targets and value not in (None, "", [], {}):
                return value
    return None


def display_value(value: Any) -> str:
    if value in (None, "", [], {}):
        return ""
    rendered = json.dumps(value, ensure_ascii=False, separators=(",", ":")) if isinstance(value, (dict, list)) else str(value)
    rendered = re.sub(r"\s+", " ", rendered).strip()
    return rendered[:180] + ("..." if len(rendered) > 180 else "")


def parse_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        stamp = float(value) / (1000 if float(value) > 10_000_000_000 else 1)
        try:
            return datetime.fromtimestamp(stamp, tz=timezone.utc)
        except (ValueError, OSError):
            return None
    text = str(value).strip().replace("Z", "+00:00")
    for candidate in (text, text[:10]):
        try:
            parsed = datetime.fromisoformat(candidate)
            return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc)
        except ValueError:
            continue
    return None


def freshness_score(extracted: dict[str, Any], now: datetime) -> tuple[float, str]:
    date_keys = [key for key in extracted if any(token in key for token in ("date", "time", "period"))]
    dates = [parsed for parsed in (parse_datetime(extracted[key]) for key in date_keys) if parsed]
    if not dates:
        return 0.25, "Date not parsed"
    latest = max(dates)
    age_days = max((now - latest).total_seconds() / 86400, 0)
    if age_days <= 1:
        return 1.0, "Current"
    if age_days <= 3:
        return 0.85, f"{round(age_days)}d old"
    if age_days <= 45:
        return 0.70, latest.date().isoformat()
    if age_days <= 120:
        return 0.55, latest.date().isoformat()
    return 0.35, latest.date().isoformat()


def sample_parameters(tool: dict[str, Any], scenario: dict[str, Any], now: datetime) -> dict[str, Any]:
    examples = tool.get("examples") or {}
    sample = examples.get("sample_parameters") if isinstance(examples, dict) else None
    explicit = dict(sample) if isinstance(sample, dict) else {}
    explicit.update(scenario["params"])
    start = (now - timedelta(days=35)).date().isoformat()
    end = now.date().isoformat()
    explicit.update({"from": start, "to": end, "start_date": start, "end_date": end, "from_date": start, "to_date": end})
    parameters = fill_default_parameters(tool, explicit)
    for param in tool.get("params") or []:
        name = str(param.get("name") or "")
        lowered = name.lower()
        if lowered in explicit:
            parameters[name] = explicit[lowered]
        elif name in explicit:
            parameters[name] = explicit[name]
        elif lowered in {"start", "startdate", "start_date", "from", "fromdate", "from_date"}:
            parameters[name] = start
        elif lowered in {"end", "enddate", "end_date", "to", "todate", "to_date"}:
            parameters[name] = end
    return parameters


def select_candidates(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for tool in results:
        if not tool.get("tool_id"):
            continue
        cost = expected_credits(tool)
        if cost and cost > QVERIS_MAX_EXPECTED_CREDITS:
            continue
        provider = provider_label(tool)
        identity = provider.lower() if provider != "Provider not stated" else str(tool["tool_id"]).split(".")[0]
        if identity in seen:
            continue
        seen.add(identity)
        selected.append(tool)
        if len(selected) >= MAX_EXECUTIONS:
            break
    return selected


def run_candidate(tool: dict[str, Any], search_id: str, scenario: dict[str, Any], now: datetime) -> dict[str, Any]:
    started = time.perf_counter()
    cost = expected_credits(tool)
    try:
        parameters = sample_parameters(tool, scenario, now)
        raw = execute_tool(str(tool["tool_id"]), SESSION_ID, parameters, search_id, max_response_size=65536)
        payload = unwrap_payload(raw)
        extracted = {field: value_by_aliases(payload, aliases) for field, aliases in scenario["fields"].items()}
        present = sum(value not in (None, "", [], {}) for value in extracted.values())
        completeness = present / len(scenario["fields"])
        fresh_score, fresh_label = freshness_score(extracted, now)
        return {
            "tool_id": str(tool["tool_id"]), "name": capability_label(tool), "provider": provider_label(tool),
            "success": True, "latency_ms": round((time.perf_counter() - started) * 1000),
            "cost_credits": cost, "completeness": completeness, "fields_present": present,
            "fields_requested": len(scenario["fields"]), "freshness_score": fresh_score,
            "freshness_label": fresh_label,
            "extracted": {key: display_value(value) for key, value in extracted.items()},
            "error": "" if completeness else "Call succeeded; requested fields were not parsed",
        }
    except Exception as error:
        return {
            "tool_id": str(tool.get("tool_id") or ""), "name": capability_label(tool),
            "provider": provider_label(tool), "success": False,
            "latency_ms": round((time.perf_counter() - started) * 1000), "cost_credits": cost,
            "completeness": 0.0, "fields_present": 0, "fields_requested": len(scenario["fields"]),
            "freshness_score": 0.0, "freshness_label": "Failed", "extracted": {},
            "error": str(error)[:500],
        }


def score_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    successful = [item for item in results if item["success"]]
    fastest = min((item["latency_ms"] for item in successful), default=1)
    known_costs = [item["cost_credits"] for item in results if item.get("cost_credits") is not None]
    cheapest = min(known_costs, default=0)
    for item in results:
        if not item["success"]:
            item["battle_score"] = 0.0
            continue
        latency_score = min(1.0, fastest / max(item["latency_ms"], 1))
        cost_score = 1 / (1 + max(float(item["cost_credits"] or 0) - cheapest, 0) / 5)
        score = (item["completeness"] * 0.50 + latency_score * 0.25 + item["freshness_score"] * 0.15 + cost_score * 0.10) * 100
        item["battle_score"] = round(score, 1)
    results.sort(key=lambda item: (item["success"], item["battle_score"], item["completeness"]), reverse=True)
    for rank, item in enumerate(results, 1):
        item["rank"] = rank
    return results


def run_test(index: int, scenario: dict[str, Any], now: datetime) -> dict[str, Any]:
    search_id, discovered = search_tools(scenario["query"], SESSION_ID, limit=20)
    attempted = [run_candidate(candidate, search_id, scenario, now) for candidate in select_candidates(discovered)]
    participants = score_results(attempted)
    winner = participants[0] if participants else None
    print(f"Battle {index}/{len(SCENARIOS)} {scenario['key']}: {winner.get('provider', 'no winner') if winner else 'no winner'} score={winner.get('battle_score', 'n/a') if winner else 'n/a'}")
    return {
        "test_no": index,
        "scenario": {key: scenario[key] for key in ("key", "label", "entity")},
        "prompt": scenario["prompt"], "discovery_prompt": scenario["query"],
        "requested_fields": list(scenario["fields"]), "search_id": search_id,
        "discovered_count": len(discovered), "attempted_count": len(attempted),
        "participants": participants, "winner": winner,
    }


def main() -> None:
    now = datetime.now(timezone.utc)
    tests = [run_test(index, scenario, now) for index, scenario in enumerate(SCENARIOS, 1)]
    result = {
        "run_date": datetime.now(RUN_TIMEZONE).strftime("%Y-%m-%d"), "run_timezone": "Asia/Shanghai",
        "generated_at": now.isoformat(), "source": "Live API calls through QVeris", "test_count": len(tests),
        "methodology": {
            "field_completeness_weight": 0.50, "live_latency_weight": 0.25,
            "freshness_weight": 0.15, "expected_cost_weight": 0.10,
            "important_note": "Each prompt has its own requested field set. Scores describe this run only; they are not universal provider rankings or a claim of financial accuracy.",
        },
        "tests": tests,
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output = OUTPUT_DIR / "api_battle_client_benchmark.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {output}")


if __name__ == "__main__":
    main()
