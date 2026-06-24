"""Fetch completed World Cup matches and mapped country ETF quotes.

The workflow is intentionally event-driven:
- If there are finished World Cup matches for the selected Asia/Shanghai date,
  it writes data/world_cup_finance.json with one record per match.
- If there are no finished matches, it writes no archive cards downstream.

Football results come from football-data.org.
ETF quotes prefer QVeris and fall back to FMP quote-short.
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = ROOT_DIR / "data" / "world_cup_finance_config.json"
OUTPUT_FILE = ROOT_DIR / "data" / "world_cup_finance.json"
RUN_TIMEZONE = ZoneInfo("Asia/Shanghai")

FOOTBALL_API_BASE_URL = os.environ.get(
    "FOOTBALL_API_BASE_URL",
    "https://api.football-data.org",
).rstrip("/")
FOOTBALL_API_KEY = os.environ.get("FOOTBALL_API_KEY") or os.environ.get("FOOTBALL_DATA_API_KEY")
FOOTBALL_COMPETITION = os.environ.get("FOOTBALL_COMPETITION", "WC")
FOOTBALL_MATCH_DATE = os.environ.get("FOOTBALL_MATCH_DATE")
FOOTBALL_MATCH_LOOKBACK_DAYS = int(os.environ.get("FOOTBALL_MATCH_LOOKBACK_DAYS", "1"))

FMP_API_URL = "https://financialmodelingprep.com/stable"
FMP_API_KEY = os.environ.get("FMP_API_KEY")

QVERIS_BASE_URL = os.environ.get("QVERIS_API_BASE_URL", "https://qveris.ai/api/v1")
QVERIS_API_KEY = os.environ.get("QVERIS_API_KEY")
QVERIS_SESSION_ID = "qveris-social-studio-world-cup-etf"
QVERIS_STOCK_QUOTE_TOOL_ID = os.environ.get("QVERIS_STOCK_QUOTE_TOOL_ID", "")
QVERIS_STOCK_QUOTE_PARAM = os.environ.get("QVERIS_STOCK_QUOTE_PARAM", "")
QVERIS_MAX_EXPECTED_CREDITS = float(os.environ.get("QVERIS_MAX_EXPECTED_CREDITS", "30"))
QVERIS_TOOL_CACHE: dict[str, str] = {}


def as_float(value: object) -> float:
    if value is None or value == "":
        return 0.0
    if isinstance(value, str):
        value = value.replace("%", "").replace(",", "")
    return float(value)


def normalized_name(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def request_json(url: str, headers: dict[str, str] | None = None) -> dict | list:
    default_headers = {"User-Agent": "qveris-social-studio/1.0"}
    default_headers.update(headers or {})
    request = Request(url, headers=default_headers)
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urlopen(request, timeout=45) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            details = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {error.code} for {url}: {details}") from error
        except URLError as error:
            last_error = error
            if attempt < 2:
                time.sleep(1 + attempt)
                continue
            break
    raise RuntimeError(f"Request failed for {url}: {last_error}")


def post_json(path: str, payload: dict, query: dict | None = None) -> dict:
    if not QVERIS_API_KEY:
        raise RuntimeError("QVERIS_API_KEY is not set")
    body = json.dumps(payload).encode("utf-8")
    suffix = f"?{urlencode(query)}" if query else ""
    request = Request(
        f"{QVERIS_BASE_URL}{path}{suffix}",
        data=body,
        headers={
            "Authorization": f"Bearer {QVERIS_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=45) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"QVeris API error {error.code} for {path}: {details}") from error


def run_date() -> datetime:
    if FOOTBALL_MATCH_DATE:
        return datetime.strptime(FOOTBALL_MATCH_DATE, "%Y-%m-%d").replace(tzinfo=RUN_TIMEZONE)
    return datetime.now(RUN_TIMEZONE)


def football_headers() -> dict[str, str]:
    if not FOOTBALL_API_KEY:
        raise RuntimeError("FOOTBALL_API_KEY is not set")
    return {"X-Auth-Token": FOOTBALL_API_KEY}


def fetch_finished_matches(target: datetime) -> list[dict]:
    # Matches in North America can end on a different UTC date than the China
    # reporting date, so fetch a two-day window and filter by Asia/Shanghai date.
    date_from = (target.date() - timedelta(days=1)).isoformat()
    date_to = target.date().isoformat()
    query = urlencode(
        {
            "dateFrom": date_from,
            "dateTo": date_to,
            "status": "FINISHED",
        }
    )
    url = f"{FOOTBALL_API_BASE_URL}/v4/competitions/{FOOTBALL_COMPETITION}/matches?{query}"
    data = request_json(url, football_headers())
    matches = data.get("matches", []) if isinstance(data, dict) else []
    selected = []
    for match in matches:
        utc_date = match.get("utcDate")
        if not utc_date:
            continue
        finished_at = datetime.fromisoformat(utc_date.replace("Z", "+00:00")).astimezone(RUN_TIMEZONE)
        if finished_at.date() == target.date():
            selected.append(match)
    return selected


def team_name(match_team: dict) -> str:
    return (
        match_team.get("name")
        or match_team.get("shortName")
        or match_team.get("tla")
        or "Unknown"
    )


def build_country_lookup(config: dict) -> dict[str, dict]:
    lookup = {}
    for country, mapping in config["country_etfs"].items():
        names = [country, *(mapping.get("aliases") or [])]
        for name in names:
            lookup[normalized_name(name)] = {"country": country, **mapping}
    return lookup


def map_team_to_etf(team: dict, lookup: dict[str, dict]) -> dict | None:
    candidates = [
        team.get("name"),
        team.get("shortName"),
        team.get("tla"),
        (team.get("area") or {}).get("name") if isinstance(team.get("area"), dict) else None,
    ]
    for candidate in candidates:
        if not candidate:
            continue
        mapped = lookup.get(normalized_name(str(candidate)))
        if mapped:
            return mapped
    return None


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
    for token in text.replace(",", " ").split():
        try:
            return float(token)
        except ValueError:
            pass
    return 0.0


def choose_symbol_param(tool: dict) -> str | None:
    preferred = ["symbol", "ticker", "stock_symbol", "stock", "query"]
    params = tool.get("params") or []
    names = [str(param.get("name", "")) for param in params]
    lowered = {name.lower(): name for name in names}
    for name in preferred:
        if name in lowered:
            return lowered[name]
    return None


def discover_qveris_quote_tool() -> tuple[str, str, str]:
    if QVERIS_STOCK_QUOTE_TOOL_ID:
        return QVERIS_STOCK_QUOTE_TOOL_ID, QVERIS_STOCK_QUOTE_PARAM or "symbol", "configured"
    if "tool_id" in QVERIS_TOOL_CACHE:
        return (
            QVERIS_TOOL_CACHE["tool_id"],
            QVERIS_TOOL_CACHE["param_name"],
            QVERIS_TOOL_CACHE.get("search_id", ""),
        )

    data = post_json(
        "/search",
        {
            "query": "ETF or stock quote by ticker symbol with latest price, daily change percentage, and volume",
            "limit": 8,
            "session_id": QVERIS_SESSION_ID,
        },
    )
    candidates = []
    search_id = data.get("search_id") or ""
    for result in data.get("results") or []:
        param_name = choose_symbol_param(result)
        if not param_name:
            continue
        cost = expected_credits(result)
        if cost and cost > QVERIS_MAX_EXPECTED_CREDITS:
            continue
        candidates.append((cost, result, param_name))
    if not candidates:
        raise RuntimeError("No low-cost QVeris ETF quote capability found")
    candidates.sort(key=lambda item: item[0])
    _, selected, param_name = candidates[0]
    QVERIS_TOOL_CACHE.update(
        {
            "tool_id": selected["tool_id"],
            "param_name": param_name,
            "search_id": search_id,
        }
    )
    print(f"QVeris quote tool: {selected.get('name')} ({selected['tool_id']})")
    return selected["tool_id"], param_name, search_id


def walk_dicts(value: object) -> list[dict]:
    dicts = []
    if isinstance(value, dict):
        dicts.append(value)
        for child in value.values():
            dicts.extend(walk_dicts(child))
    elif isinstance(value, list):
        for child in value:
            dicts.extend(walk_dicts(child))
    return dicts


def key_norm(value: str) -> str:
    return "".join(char for char in value.lower() if char.isalnum())


def find_numeric(payload: dict, names: list[str]) -> float:
    targets = [key_norm(name) for name in names]
    for item in walk_dicts(payload):
        normalized = {key_norm(str(key)): val for key, val in item.items()}
        for target in targets:
            if target in normalized:
                try:
                    return as_float(normalized[target])
                except (TypeError, ValueError):
                    pass
    return 0.0


def fetch_qveris_quote(symbol: str) -> dict | None:
    if not QVERIS_API_KEY:
        return None
    tool_id, param_name, search_id = discover_qveris_quote_tool()
    data = post_json(
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
        ["changePercent", "changesPercentage", "regularMarketChangePercent", "10. change percent"],
    )
    volume = int(find_numeric(result, ["volume", "regularMarketVolume", "06. volume"]))
    if not price:
        raise RuntimeError(f"QVeris result did not include price for {symbol}")
    if not change_pct and price and change:
        previous = price - change
        change_pct = change / previous * 100 if previous else 0
    return {
        "symbol": symbol,
        "price": price,
        "change": change,
        "change_pct": change_pct,
        "volume": volume,
        "source": "QVeris API",
    }


def fmp_get(path: str, params: dict) -> list | dict:
    if not FMP_API_KEY:
        raise RuntimeError("FMP_API_KEY is not set")
    query = {"apikey": FMP_API_KEY}
    query.update(params)
    url = f"{FMP_API_URL}/{path}?{urlencode(query)}"
    return request_json(url)


def fetch_fmp_quote(symbol: str) -> dict | None:
    data = fmp_get("quote-short", {"symbol": symbol})
    if not isinstance(data, list) or not data:
        return None
    raw = data[0]
    price = as_float(raw.get("price"))
    change = as_float(raw.get("change"))
    previous = price - change
    return {
        "symbol": str(raw.get("symbol") or symbol).upper(),
        "price": price,
        "change": change,
        "change_pct": change / previous * 100 if previous else 0,
        "volume": int(as_float(raw.get("volume"))),
        "source": "FMP quote-short",
    }


def fetch_yahoo_quote(symbol: str) -> dict | None:
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{symbol}?range=5d&interval=1d"
    )
    data = request_json(url)
    chart = data.get("chart", {}) if isinstance(data, dict) else {}
    results = chart.get("result") or []
    if not results:
        return None
    result = results[0]
    meta = result.get("meta") or {}
    quote_series = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    closes = [value for value in quote_series.get("close", []) if value is not None]
    volumes = [value for value in quote_series.get("volume", []) if value is not None]

    price = as_float(meta.get("regularMarketPrice") or (closes[-1] if closes else 0))
    previous = as_float(meta.get("chartPreviousClose") or (closes[-2] if len(closes) >= 2 else 0))
    if not price:
        return None
    change = price - previous if previous else 0
    change_pct = change / previous * 100 if previous else 0
    return {
        "symbol": symbol.upper(),
        "price": price,
        "change": change,
        "change_pct": change_pct,
        "volume": int(as_float(meta.get("regularMarketVolume") or (volumes[-1] if volumes else 0))),
        "source": "Yahoo Finance chart fallback",
    }


def fetch_quote(symbol: str) -> dict | None:
    try:
        quote = fetch_qveris_quote(symbol)
        if quote:
            return quote
    except RuntimeError as error:
        print(f"Warning: QVeris quote unavailable for {symbol}: {error}")
    try:
        return fetch_fmp_quote(symbol)
    except RuntimeError as error:
        print(f"Warning: FMP quote unavailable for {symbol}: {error}")
    try:
        return fetch_yahoo_quote(symbol)
    except RuntimeError as error:
        print(f"Warning: Yahoo quote unavailable for {symbol}: {error}")
        return None


def match_status(match: dict) -> str:
    return str(match.get("status") or "").upper()


def match_score(match: dict) -> tuple[int | None, int | None]:
    full_time = ((match.get("score") or {}).get("fullTime") or {})
    return full_time.get("home"), full_time.get("away")


def match_label(match: dict) -> str:
    home = team_name(match.get("homeTeam") or {})
    away = team_name(match.get("awayTeam") or {})
    home_score, away_score = match_score(match)
    if home_score is None or away_score is None:
        return f"{home} vs {away}"
    return f"{home} {home_score}-{away_score} {away}"


def result_label(home_score: int | None, away_score: int | None) -> str:
    if home_score is None or away_score is None:
        return "Result pending"
    if home_score > away_score:
        return "home_win"
    if away_score > home_score:
        return "away_win"
    return "draw"


def build_match_record(match: dict, lookup: dict[str, dict]) -> dict | None:
    if match_status(match) != "FINISHED":
        return None
    home_team = match.get("homeTeam") or {}
    away_team = match.get("awayTeam") or {}
    home_map = map_team_to_etf(home_team, lookup)
    away_map = map_team_to_etf(away_team, lookup)
    if not home_map or not away_map:
        print(f"Skipping unmapped match: {team_name(home_team)} vs {team_name(away_team)}")
        return None

    home_quote = fetch_quote(home_map["ticker"])
    away_quote = fetch_quote(away_map["ticker"])
    if not home_quote or not away_quote:
        print(f"Skipping match with missing ETF quote: {match_label(match)}")
        return None

    home_score, away_score = match_score(match)
    utc_date = match.get("utcDate", "")
    local_datetime = (
        datetime.fromisoformat(utc_date.replace("Z", "+00:00")).astimezone(RUN_TIMEZONE).isoformat()
        if utc_date
        else ""
    )
    return {
        "id": str(match.get("id") or f"{home_map['country']}-{away_map['country']}-{utc_date}"),
        "utc_date": utc_date,
        "local_datetime": local_datetime,
        "label": match_label(match),
        "result": result_label(home_score, away_score),
        "home": {
            "team": team_name(home_team),
            "country": home_map["country"],
            "score": home_score,
            "etf": home_map["ticker"],
            "etf_name": home_map.get("etf_name", home_map["ticker"]),
            "is_proxy": bool(home_map.get("is_proxy", False)),
            "proxy_note": home_map.get("proxy_note", ""),
            "quote": home_quote,
        },
        "away": {
            "team": team_name(away_team),
            "country": away_map["country"],
            "score": away_score,
            "etf": away_map["ticker"],
            "etf_name": away_map.get("etf_name", away_map["ticker"]),
            "is_proxy": bool(away_map.get("is_proxy", False)),
            "proxy_note": away_map.get("proxy_note", ""),
            "quote": away_quote,
        },
    }


def main() -> dict:
    if not FOOTBALL_API_KEY:
        raise RuntimeError("FOOTBALL_API_KEY is not set")
    if not QVERIS_API_KEY and not FMP_API_KEY:
        raise RuntimeError("Set QVERIS_API_KEY or FMP_API_KEY")

    config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    target = run_date()
    match_target = target - timedelta(days=FOOTBALL_MATCH_LOOKBACK_DAYS)
    raw_matches = fetch_finished_matches(match_target)
    lookup = build_country_lookup(config)
    match_records = []
    for match in raw_matches:
        record = build_match_record(match, lookup)
        if record:
            match_records.append(record)

    output = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "date": target.strftime("%Y-%m-%d"),
        "market_check_date": target.strftime("%Y-%m-%d"),
        "match_date": match_target.strftime("%Y-%m-%d"),
        "run_timezone": "Asia/Shanghai",
        "source": "football-data.org, QVeris API with FMP/Yahoo fallback",
        "event": config.get("event", "2026 FIFA World Cup"),
        "matches": match_records,
    }
    OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {OUTPUT_FILE}")
    print(f"Market check date: {output['market_check_date']}")
    print(f"Match date checked: {output['match_date']}")
    print(f"Finished matches found: {len(raw_matches)}")
    print(f"Mapped ETF cards: {len(match_records)}")
    for record in match_records:
        print(
            f"  {record['label']} | "
            f"${record['home']['etf']} {record['home']['quote']['change_pct']:+.2f}% / "
            f"${record['away']['etf']} {record['away']['quote']['change_pct']:+.2f}%"
        )
    return output


if __name__ == "__main__":
    main()
