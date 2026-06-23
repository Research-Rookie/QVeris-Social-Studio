"""Fetch FCF yield comparison data from Financial Modeling Prep."""

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
OUTPUT_FILE = ROOT_DIR / "data" / "fcf_yield.json"
RUN_TIMEZONE = ZoneInfo("Asia/Shanghai")
DEFAULT_SYMBOLS = "PYPL,ADBE"
DEFAULT_QUARTER_LIMIT = os.environ.get("FCF_QUARTER_LIMIT", "5")


def fmp_get(path: str, api_key: str, params: dict | None = None) -> list | dict:
    query = {"apikey": api_key}
    if params:
        query.update(params)

    url = f"{FMP_API_URL}/{path}?{urlencode(query)}"
    try:
        with urlopen(url, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"FMP API error {error.code} for {path}: {details}") from error

    if isinstance(data, dict) and ("Error Message" in data or "Note" in data):
        raise RuntimeError(f"Unexpected FMP response for {path}: {data}")
    return data


def get_symbols() -> list[str]:
    raw = os.environ.get("FCF_SYMBOLS", DEFAULT_SYMBOLS)
    symbols = [symbol.strip().upper() for symbol in raw.split(",") if symbol.strip()]
    if len(symbols) != 2:
        raise RuntimeError("FCF_SYMBOLS must contain exactly two tickers, e.g. PYPL,ADBE")
    return symbols


def as_float(value: object) -> float:
    if value is None or value == "":
        return 0.0
    return float(value)


def free_cash_flow(statement: dict) -> float:
    direct = statement.get("freeCashFlow")
    if direct not in (None, ""):
        return as_float(direct)

    operating_cash_flow = as_float(
        statement.get("netCashProvidedByOperatingActivities")
        or statement.get("operatingCashFlow")
    )
    capital_expenditure = as_float(statement.get("capitalExpenditure"))
    return operating_cash_flow + capital_expenditure


def market_cap_from(profile: dict, quote: dict) -> float:
    candidates = [
        quote.get("marketCap"),
        profile.get("mktCap"),
        profile.get("marketCap"),
    ]
    for value in candidates:
        cap = as_float(value)
        if cap > 0:
            return cap
    raise RuntimeError("Could not find market cap in FMP profile or quote response")


def company_name(symbol: str, profile: dict) -> str:
    return str(profile.get("companyName") or profile.get("company_name") or symbol)


def build_company(symbol: str, api_key: str) -> dict:
    cash_flow = fmp_get(
        "cash-flow-statement",
        api_key,
        {"symbol": symbol, "period": "quarter", "limit": DEFAULT_QUARTER_LIMIT},
    )
    profile_data = fmp_get("profile", api_key, {"symbol": symbol})
    quote_data = fmp_get("quote", api_key, {"symbol": symbol})

    if not isinstance(cash_flow, list) or len(cash_flow) < 4:
        raise RuntimeError(f"Not enough quarterly cash-flow data for {symbol}")

    profile = profile_data[0] if isinstance(profile_data, list) and profile_data else {}
    quote = quote_data[0] if isinstance(quote_data, list) and quote_data else {}
    market_cap = market_cap_from(profile, quote)

    quarters = [
        {
            "date": str(item.get("date") or item.get("calendarYear") or ""),
            "fcf": free_cash_flow(item),
        }
        for item in cash_flow
    ]

    latest_ttm_fcf = sum(quarter["fcf"] for quarter in quarters[:4])
    latest_fcf_yield = latest_ttm_fcf / market_cap * 100

    history = []
    for index in range(0, len(quarters) - 3):
        ttm_fcf = sum(quarter["fcf"] for quarter in quarters[index : index + 4])
        history.append(
            {
                "date": quarters[index]["date"],
                "ttm_fcf": ttm_fcf,
                "fcf_yield": ttm_fcf / market_cap * 100,
            }
        )

    return {
        "symbol": symbol,
        "name": company_name(symbol, profile),
        "market_cap": market_cap,
        "price": as_float(quote.get("price") or profile.get("price")),
        "latest_ttm_fcf": latest_ttm_fcf,
        "latest_fcf_yield": latest_fcf_yield,
        "history": history,
    }


def main() -> dict:
    api_key = os.environ.get("FMP_API_KEY")
    if not api_key:
        raise RuntimeError("FMP_API_KEY is not set")

    symbols = get_symbols()
    now = datetime.now(timezone.utc)
    run_now = datetime.now(RUN_TIMEZONE)
    companies = [build_company(symbol, api_key) for symbol in symbols]
    companies.sort(key=lambda company: company["latest_fcf_yield"], reverse=True)

    output = {
        "updated_at": now.isoformat(),
        "date": run_now.strftime("%Y-%m-%d"),
        "run_timezone": "Asia/Shanghai",
        "source": "Financial Modeling Prep",
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
