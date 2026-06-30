"""Fetch Polymarket activity pulse data from QVeris."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from qveris_finance import as_float, execute_tool, walk_dicts, walk_lists


ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_FILE = ROOT_DIR / "data" / "polymarket_pulse.json"
RUN_TIMEZONE = ZoneInfo("Asia/Shanghai")
SESSION_ID = "qveris-social-studio-polymarket-pulse"
VOLUME_TOOL_ID = os.environ.get(
    "QVERIS_POLYMARKET_VOLUME_TOOL_ID",
    "polymarket.builders.volume.list.v1.38f84687",
)
OPEN_INTEREST_TOOL_ID = os.environ.get(
    "QVERIS_POLYMARKET_OPEN_INTEREST_TOOL_ID",
    "polymarket.open_interest.list.v1.f613174f",
)


def value_by_any(item: dict[str, Any], names: list[str]) -> Any:
    normalized = {
        "".join(ch for ch in str(key).lower() if ch.isalnum()): value
        for key, value in item.items()
    }
    for name in names:
        key = "".join(ch for ch in name.lower() if ch.isalnum())
        if key in normalized:
            return normalized[key]
    return None


def find_date(item: dict[str, Any]) -> str:
    value = value_by_any(
        item,
        ["date", "day", "timestamp", "time", "created_at", "createdAt", "period"],
    )
    return str(value or "")


def find_volume(item: dict[str, Any]) -> float:
    return as_float(
        value_by_any(
            item,
            ["volume", "dailyVolume", "daily_volume", "amount", "value", "totalVolume"],
        )
    )


def find_open_interest(item: dict[str, Any]) -> float:
    return as_float(
        value_by_any(
            item,
            ["openInterest", "open_interest", "oi", "value", "amount"],
        )
    )


def title_for(item: dict[str, Any]) -> str:
    value = value_by_any(
        item,
        ["title", "question", "name", "market", "marketTitle", "market_title", "slug"],
    )
    title = " ".join(str(value or "Polymarket market").split())
    return title[:78] + "..." if len(title) > 81 else title


def extract_volume_series(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for collection in walk_lists(payload):
        parsed = []
        for item in collection:
            if not isinstance(item, dict):
                continue
            volume = find_volume(item)
            if volume <= 0:
                continue
            parsed.append({"date": find_date(item), "volume": volume})
        if len(parsed) >= 1:
            rows.extend(parsed)

    if not rows:
        for item in walk_dicts(payload):
            volume = find_volume(item)
            if volume > 0:
                rows.append({"date": find_date(item), "volume": volume})

    seen = set()
    unique = []
    for row in rows:
        identity = (row["date"], row["volume"])
        if identity in seen:
            continue
        seen.add(identity)
        unique.append(row)
    return unique[-14:]


def extract_open_interest(payload: dict[str, Any]) -> tuple[float, list[dict[str, Any]]]:
    markets = []
    total = 0.0
    for item in walk_dicts(payload):
        oi = find_open_interest(item)
        if oi <= 0:
            continue
        title = title_for(item)
        if title == "Polymarket market" and len(item) <= 2:
            total = max(total, oi)
            continue
        markets.append({"title": title, "open_interest": oi})
        total += oi

    markets.sort(key=lambda item: item["open_interest"], reverse=True)
    return total, markets[:4]


def money_short(value: float) -> str:
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.1f}B"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"${value / 1_000:.1f}K"
    if value > 0:
        return f"${value:.0f}"
    return "n/a"


def pct_change(current: float, previous: float) -> float:
    if previous <= 0:
        return 0.0
    return (current - previous) / previous * 100


def activity_label(change: float) -> str:
    if change >= 20:
        return "Heating up"
    if change >= 5:
        return "Rising"
    if change <= -20:
        return "Cooling fast"
    if change <= -5:
        return "Cooling"
    return "Stable"


def takeaway(label: str, change: float, open_interest: float) -> str:
    direction = "higher" if change >= 0 else "lower"
    if open_interest > 0:
        return (
            f"Polymarket activity is {label.lower()} with volume {direction} "
            f"and {money_short(open_interest)} in tracked open interest."
        )
    return f"Polymarket activity is {label.lower()} with volume {direction} versus the prior point."


def fetch_volume() -> dict[str, Any]:
    last_error = None
    for time_period in ["1m", "30d", "7d", "1d"]:
        try:
            return execute_tool(
                VOLUME_TOOL_ID,
                SESSION_ID,
                {"timePeriod": time_period},
                max_response_size=65536,
            )
        except RuntimeError as error:
            last_error = error
            print(f"Volume retry after {time_period}: {error}")
    raise RuntimeError(f"Could not fetch Polymarket volume: {last_error}")


def fetch_open_interest() -> dict[str, Any]:
    try:
        return execute_tool(
            OPEN_INTEREST_TOOL_ID,
            SESSION_ID,
            {},
            max_response_size=65536,
        )
    except RuntimeError as error:
        print(f"Open interest unavailable: {error}")
        return {}


def main() -> dict[str, Any]:
    volume_payload = fetch_volume()
    open_interest_payload = fetch_open_interest()

    volume_series = extract_volume_series(volume_payload)
    if not volume_series:
        raise RuntimeError("QVeris returned Polymarket volume data, but no volume rows were parsed.")

    current_volume = volume_series[-1]["volume"]
    previous_volume = volume_series[-2]["volume"] if len(volume_series) > 1 else 0.0
    volume_change = pct_change(current_volume, previous_volume)
    label = activity_label(volume_change)
    open_interest_total, top_markets = extract_open_interest(open_interest_payload)

    now = datetime.now(timezone.utc)
    run_now = datetime.now(RUN_TIMEZONE)
    output = {
        "updated_at": now.isoformat(),
        "date": run_now.strftime("%Y-%m-%d"),
        "run_timezone": "Asia/Shanghai",
        "source": "QVeris API via Polymarket",
        "title": "Polymarket Activity Pulse",
        "current_volume": current_volume,
        "previous_volume": previous_volume,
        "volume_change_pct": volume_change,
        "activity_label": label,
        "open_interest": open_interest_total,
        "top_markets": top_markets,
        "volume_series": volume_series,
        "takeaway": takeaway(label, volume_change, open_interest_total),
    }
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Saved {OUTPUT_FILE}")
    print(f"Volume: {money_short(current_volume)} ({volume_change:+.1f}%)")
    print(f"Open interest: {money_short(open_interest_total)}")
    return output


if __name__ == "__main__":
    main()
