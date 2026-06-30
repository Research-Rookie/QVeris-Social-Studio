"""Fetch FCF yield comparison data from QVeris."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from qveris_finance import as_float, execute_best_tool, find_numeric, find_text, walk_dicts


ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_FILE = ROOT_DIR / "data" / "fcf_yield.json"
RUN_TIMEZONE = ZoneInfo("Asia/Shanghai")
DEFAULT_SYMBOLS = "PYPL,ADBE"
SESSION_ID = "qveris-social-studio-fcf-yield"
QVERIS_FCF_TOOL_ID = os.environ.get("QVERIS_FCF_TOOL_ID", "")
DEFAULT_QUARTER_LIMIT = int(os.environ.get("FCF_QUARTER_LIMIT", "5"))


def get_symbols() -> list[str]:
    raw = os.environ.get("FCF_SYMBOLS", DEFAULT_SYMBOLS)
    symbols = [symbol.strip().upper() for symbol in raw.split(",") if symbol.strip()]
    if len(symbols) != 2:
        raise RuntimeError("FCF_SYMBOLS must contain exactly two tickers, e.g. PYPL,ADBE")
    return symbols


def key_norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def value_by_names(item: dict, names: list[str]) -> object:
    normalized = {key_norm(str(key)): val for key, val in item.items()}
    for name in names:
        target = key_norm(name)
        if target in normalized:
            return normalized[target]
    return None


def date_from(item: dict) -> str:
    value = value_by_names(
        item,
        ["date", "fiscalDateEnding", "period", "calendarDate", "reportDate", "fillingDate"],
    )
    return str(value or "")


def free_cash_flow_from(item: dict) -> float:
    direct = as_float(
        value_by_names(
            item,
            [
                "freeCashFlow",
                "free_cash_flow",
                "fcf",
                "TTM Free Cash Flow",
                "trailingTwelveMonthsFreeCashFlow",
            ],
        )
    )
    if direct:
        return direct

    operating_cash_flow = as_float(
        value_by_names(
            item,
            [
                "netCashProvidedByOperatingActivities",
                "operatingCashFlow",
                "cashFlowFromOperations",
                "net_cash_from_operating_activities",
            ],
        )
    )
    capital_expenditure = as_float(
        value_by_names(
            item,
            ["capitalExpenditure", "capital_expenditure", "capex"],
        )
    )
    if operating_cash_flow or capital_expenditure:
        return operating_cash_flow + capital_expenditure
    return 0.0


def extract_quarters(payload: dict) -> list[dict]:
    quarters = []
    seen = set()
    for item in walk_dicts(payload):
        date = date_from(item)
        fcf = free_cash_flow_from(item)
        if not date or not fcf:
            continue
        key = (date, fcf)
        if key in seen:
            continue
        seen.add(key)
        quarters.append({"date": date, "fcf": fcf})
    quarters.sort(key=lambda row: row["date"], reverse=True)
    return quarters[: max(DEFAULT_QUARTER_LIMIT, 4)]


def extract_market_cap(payload: dict) -> float:
    market_cap = find_numeric(
        payload,
        [
            "marketCap",
            "market_cap",
            "mktCap",
            "market capitalization",
            "marketCapitalization",
        ],
    )
    if market_cap <= 0:
        raise RuntimeError("QVeris result did not include market cap")
    return market_cap


def extract_company_name(symbol: str, payload: dict) -> str:
    return (
        find_text(payload, ["companyName", "company_name", "name", "longName", "shortName"])
        or symbol
    )


def fetch_company_payload(symbol: str) -> dict:
    query = (
        "Stock financial fundamentals by ticker with quarterly free cash flow, "
        "TTM free cash flow, market capitalization, price, and company name"
    )
    return execute_best_tool(
        query,
        SESSION_ID,
        {
            "symbol": symbol,
            "ticker": symbol,
            "query": f"{symbol} quarterly free cash flow market capitalization",
            "limit": DEFAULT_QUARTER_LIMIT,
            "market": "US",
        },
        configured_tool_id=QVERIS_FCF_TOOL_ID,
        max_response_size=65536,
    )


def build_history(quarters: list[dict], market_cap: float, latest_ttm_fcf: float) -> list[dict]:
    history = []
    if len(quarters) >= 4:
        for index in range(0, len(quarters) - 3):
            ttm_fcf = sum(quarter["fcf"] for quarter in quarters[index : index + 4])
            history.append(
                {
                    "date": quarters[index]["date"],
                    "ttm_fcf": ttm_fcf,
                    "fcf_yield": ttm_fcf / market_cap * 100,
                }
            )

    if not history:
        today = datetime.now(RUN_TIMEZONE).strftime("%Y-%m-%d")
        history.append(
            {
                "date": today,
                "ttm_fcf": latest_ttm_fcf,
                "fcf_yield": latest_ttm_fcf / market_cap * 100,
            }
        )
    if len(history) == 1:
        history.append({**history[0], "date": datetime.now(RUN_TIMEZONE).strftime("%Y-%m-%d")})
    return history


def build_company(symbol: str) -> dict:
    payload = fetch_company_payload(symbol)
    market_cap = extract_market_cap(payload)
    quarters = extract_quarters(payload)

    latest_ttm_fcf = find_numeric(
        payload,
        [
            "ttmFreeCashFlow",
            "TTM Free Cash Flow",
            "trailingTwelveMonthsFreeCashFlow",
            "latest_ttm_fcf",
        ],
    )
    if latest_ttm_fcf <= 0 and len(quarters) >= 4:
        latest_ttm_fcf = sum(quarter["fcf"] for quarter in quarters[:4])
    if latest_ttm_fcf <= 0:
        raise RuntimeError(f"QVeris result did not include enough FCF data for {symbol}")

    price = find_numeric(payload, ["price", "latestPrice", "currentPrice", "regularMarketPrice"])
    latest_fcf_yield = latest_ttm_fcf / market_cap * 100

    return {
        "symbol": symbol,
        "name": extract_company_name(symbol, payload),
        "market_cap": market_cap,
        "price": price,
        "latest_ttm_fcf": latest_ttm_fcf,
        "latest_fcf_yield": latest_fcf_yield,
        "history": build_history(quarters, market_cap, latest_ttm_fcf),
    }


def main() -> dict:
    symbols = get_symbols()
    now = datetime.now(timezone.utc)
    run_now = datetime.now(RUN_TIMEZONE)
    companies = [build_company(symbol) for symbol in symbols]
    companies.sort(key=lambda company: company["latest_fcf_yield"], reverse=True)

    output = {
        "updated_at": now.isoformat(),
        "date": run_now.strftime("%Y-%m-%d"),
        "run_timezone": "Asia/Shanghai",
        "source": "QVeris API",
        "symbols": symbols,
        "companies": companies,
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Saved {OUTPUT_FILE}")
    for company in companies:
        print(
            f"  ${company['symbol']} FCF Yield "
            f"{company['latest_fcf_yield']:.2f}%"
        )

    return output


if __name__ == "__main__":
    main()
