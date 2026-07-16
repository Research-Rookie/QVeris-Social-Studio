"""Build an Earnings Reality Check from QVeris earnings and price data."""

from __future__ import annotations

import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from qveris_finance import as_float, execute_tool


ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_FILE = ROOT_DIR / "data" / "earnings_reality_check.json"
RUN_TIMEZONE = ZoneInfo("Asia/Shanghai")
SESSION_ID = "qveris-social-studio-earnings-reality"
EARNINGS_TOOL_ID = os.environ.get(
    "QVERIS_EARNINGS_TOOL_ID", "alphavantage.earnings.retrieve.v1.7aca3c4a"
)
PRICE_TOOL_ID = os.environ.get(
    "QVERIS_DAILY_PRICE_TOOL_ID", "alphavantage.time-series.daily.v1"
)
DEFAULT_SYMBOLS = "AAPL,MSFT,NVDA,AMZN,GOOGL,META,TSLA,NFLX,JPM,WMT"

COMPANY_NAMES = {
    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "NVDA": "NVIDIA",
    "AMZN": "Amazon",
    "GOOGL": "Alphabet",
    "META": "Meta Platforms",
    "TSLA": "Tesla",
    "NFLX": "Netflix",
    "JPM": "JPMorgan Chase",
    "WMT": "Walmart",
}


def unwrap(payload: Any) -> Any:
    current = payload
    for _ in range(4):
        if not isinstance(current, dict):
            break
        if isinstance(current.get("data"), (dict, list)):
            current = current["data"]
            continue
        if isinstance(current.get("result"), (dict, list)):
            current = current["result"]
            continue
        break
    return current


def symbols() -> list[str]:
    raw = os.environ.get("EARNINGS_SYMBOLS", DEFAULT_SYMBOLS)
    return [item.strip().upper() for item in raw.split(",") if item.strip()]


def parse_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def fetch_latest_earnings(symbol: str, today: date) -> dict[str, Any] | None:
    payload = execute_tool(
        EARNINGS_TOOL_ID,
        SESSION_ID,
        {"function": "EARNINGS", "symbol": symbol},
        max_response_size=65536,
    )
    data = unwrap(payload)
    if not isinstance(data, dict):
        return None
    rows = data.get("quarterlyEarnings") or data.get("quarterly_earnings") or []
    candidates = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        reported_date = parse_date(row.get("reportedDate") or row.get("reported_date"))
        actual = as_float(row.get("reportedEPS") or row.get("actualEPS"))
        estimate = as_float(row.get("estimatedEPS") or row.get("epsEstimate"))
        if reported_date and reported_date <= today and actual and estimate:
            candidates.append(
                {
                    "symbol": symbol,
                    "company": COMPANY_NAMES.get(symbol, symbol),
                    "reported_date": reported_date.isoformat(),
                    "fiscal_date": str(row.get("fiscalDateEnding") or ""),
                    "report_time": str(row.get("reportTime") or "unknown"),
                    "actual_eps": actual,
                    "estimated_eps": estimate,
                    "surprise": as_float(row.get("surprise")) or actual - estimate,
                    "surprise_pct": as_float(row.get("surprisePercentage"))
                    or ((actual - estimate) / abs(estimate) * 100 if estimate else 0),
                }
            )
    candidates.sort(key=lambda item: item["reported_date"], reverse=True)
    return candidates[0] if candidates else None


def fetch_price_series(symbol: str) -> dict[str, float]:
    payload = execute_tool(
        PRICE_TOOL_ID,
        SESSION_ID,
        {
            "function": "TIME_SERIES_DAILY",
            "symbol": symbol,
            "outputsize": "compact",
            "datatype": "json",
        },
        max_response_size=65536,
    )
    data = unwrap(payload)
    if not isinstance(data, dict):
        return {}
    series = data.get("Time Series (Daily)") or data.get("time_series_daily") or {}
    prices: dict[str, float] = {}
    if isinstance(series, dict):
        for day, row in series.items():
            if isinstance(row, dict):
                close = as_float(row.get("4. close") or row.get("close"))
                if close:
                    prices[str(day)[:10]] = close
    return prices


def calculate_reaction(earnings: dict[str, Any], prices: dict[str, float]) -> dict[str, Any]:
    report_date = parse_date(earnings["reported_date"])
    ordered = sorted((parse_date(day), day, close) for day, close in prices.items() if parse_date(day))
    prior = [row for row in ordered if row[0] < report_date]
    same_or_after = [row for row in ordered if row[0] >= report_date]
    after = [row for row in ordered if row[0] > report_date]
    report_time = earnings.get("report_time", "").lower()

    if "post" in report_time:
        base_rows = [row for row in ordered if row[0] <= report_date]
        reaction_rows = after
    else:
        base_rows = prior
        reaction_rows = same_or_after

    if not base_rows or not reaction_rows:
        return {"available": False, "change_pct": 0.0, "base_date": "", "reaction_date": ""}
    base = base_rows[-1]
    reaction = reaction_rows[0]
    change_pct = (reaction[2] / base[2] - 1) * 100
    return {
        "available": True,
        "base_date": base[1],
        "base_close": base[2],
        "reaction_date": reaction[1],
        "reaction_close": reaction[2],
        "change_pct": change_pct,
    }


def verdict(surprise_pct: float, reaction: dict[str, Any]) -> tuple[str, str]:
    if not reaction.get("available"):
        return "Price pending", "The earnings result is in; the first full market reaction is not available yet."
    move = float(reaction.get("change_pct") or 0)
    beat = surprise_pct >= 0.5
    miss = surprise_pct <= -0.5
    rewarded = move >= 0.3
    punished = move <= -0.3
    if beat and rewarded:
        return "Beat and rewarded", "Earnings cleared expectations and the next session confirmed the result."
    if beat and punished:
        return "Beat but sold off", "EPS beat the Street, but the stock fell. Expectations were likely even higher."
    if miss and rewarded:
        return "Miss but recovered", "EPS missed expectations, yet buyers looked through the headline."
    if miss and punished:
        return "Miss and punished", "The earnings miss and the next-session price reaction pointed the same way."
    return "Mixed reaction", "The earnings surprise or the price move was too small for a decisive confirmation."


def main() -> dict[str, Any]:
    run_now = datetime.now(RUN_TIMEZONE)
    candidates = []
    errors = []
    for symbol in symbols():
        try:
            result = fetch_latest_earnings(symbol, run_now.date())
            if result:
                candidates.append(result)
        except Exception as error:
            errors.append(f"{symbol}: {error}")
    if not candidates:
        raise RuntimeError("No usable reported earnings returned by QVeris. " + " | ".join(errors))

    candidates.sort(key=lambda item: (item["reported_date"], abs(item["surprise_pct"])), reverse=True)
    selected = candidates[0]
    prices = fetch_price_series(selected["symbol"])
    reaction = calculate_reaction(selected, prices)
    label, takeaway = verdict(selected["surprise_pct"], reaction)
    output = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "date": run_now.strftime("%Y-%m-%d"),
        "run_timezone": "Asia/Shanghai",
        "source": "QVeris API via earnings history and daily prices",
        "title": "Earnings Reality Check",
        **selected,
        "price_reaction": reaction,
        "verdict": label,
        "takeaway": takeaway,
        "universe_size": len(symbols()),
        "candidate_count": len(candidates),
    }
    OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {OUTPUT_FILE}")
    print(f"${selected['symbol']} EPS {selected['actual_eps']:.2f} vs {selected['estimated_eps']:.2f}; {label}")
    return output


if __name__ == "__main__":
    main()
