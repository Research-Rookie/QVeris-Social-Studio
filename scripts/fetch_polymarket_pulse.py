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
SERIES_TOOL_ID = os.environ.get(
    "QVERIS_POLYMARKET_SERIES_TOOL_ID",
    "polymarket.series.list.v1.7e5c1eeb",
)
MARKETS_TOOL_ID = os.environ.get(
    "QVERIS_POLYMARKET_MARKETS_TOOL_ID",
    "polymarket.gamma_get_markets.v1",
)
EVENTS_TOOL_ID = os.environ.get(
    "QVERIS_POLYMARKET_EVENTS_TOOL_ID",
    "polymarket.events.list.v1.eafcc524",
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


def parse_embedded_payload(payload: Any) -> Any:
    if isinstance(payload, dict):
        content = payload.get("truncated_content") or payload.get("content") or payload.get("data")
        if isinstance(content, str) and content.strip().startswith(("[", "{")):
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return payload
    return payload


def find_theme(item: dict[str, Any]) -> str:
    value = value_by_any(
        item,
        [
            "category",
            "series",
            "seriesTitle",
            "series_title",
            "tag",
            "tagSlug",
            "tag_slug",
            "title",
            "slug",
        ],
    )
    theme = " ".join(str(value or "General").replace("-", " ").split())
    if not theme or theme.lower() in {"none", "null"}:
        return "General"
    return theme[:30]


def find_activity(item: dict[str, Any]) -> float:
    return max(
        find_volume(item),
        find_open_interest(item),
        as_float(value_by_any(item, ["liquidity", "liquidityNum", "liquidity_num"])),
    )


def extract_theme_rows(payload: Any) -> list[dict[str, Any]]:
    theme_totals: dict[str, float] = {}
    for item in walk_dicts(parse_embedded_payload(payload)):
        activity = find_activity(item)
        if activity <= 0:
            continue
        theme = find_theme(item)
        theme_totals[theme] = theme_totals.get(theme, 0.0) + activity

    rows = [
        {"theme": theme, "activity": activity}
        for theme, activity in theme_totals.items()
        if activity > 0
    ]
    rows.sort(key=lambda row: row["activity"], reverse=True)
    return rows[:5]


def extract_market_rows(payload: Any) -> list[dict[str, Any]]:
    rows = []
    seen = set()
    for item in walk_dicts(parse_embedded_payload(payload)):
        title = title_for(item)
        activity = find_activity(item)
        market_id = str(
            value_by_any(item, ["id", "market", "marketId", "conditionId", "slug"]) or title
        )
        if title == "Polymarket market" or activity <= 0 or market_id in seen:
            continue
        seen.add(market_id)
        rows.append(
            {
                "title": title,
                "theme": find_theme(item),
                "activity": activity,
                "volume": find_volume(item),
                "open_interest": find_open_interest(item),
                "market_id": market_id,
            }
        )

    rows.sort(key=lambda row: row["activity"], reverse=True)
    return rows[:5]


def extract_volume_series(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    payload = parse_embedded_payload(payload)
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
    payload = parse_embedded_payload(payload)
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
    parameter_sets = [
        {"timePeriod": "day"},
        {"timePeriod": "week"},
        {"timePeriod": "month"},
        {"timePeriod": "all"},
        {"timePeriod": "daily"},
        {"timePeriod": "weekly"},
        {"timePeriod": "monthly"},
        {"timePeriod": "ONE_DAY"},
        {"timePeriod": "ONE_WEEK"},
        {"timePeriod": "ONE_MONTH"},
        {},
    ]
    for parameters in parameter_sets:
        try:
            return execute_tool(
                VOLUME_TOOL_ID,
                SESSION_ID,
                parameters,
                max_response_size=65536,
            )
        except RuntimeError as error:
            last_error = error
            print(f"Volume retry after {parameters or 'no parameters'}: {error}")
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


def fetch_series() -> dict[str, Any]:
    try:
        return execute_tool(
            SERIES_TOOL_ID,
            SESSION_ID,
            {},
            max_response_size=65536,
        )
    except RuntimeError as error:
        print(f"Series unavailable: {error}")
        return {}


def fetch_markets() -> dict[str, Any]:
    parameter_sets = [
        {"limit": 50, "order": "volume", "ascending": False, "active": True, "closed": False},
        {"limit": 50, "order": "volume", "ascending": False},
        {"limit": 50, "order": "createdAt", "ascending": False, "active": True},
        {"limit": 50, "active": True},
        {"limit": 50},
    ]
    for parameters in parameter_sets:
        try:
            return execute_tool(
                MARKETS_TOOL_ID,
                SESSION_ID,
                parameters,
                max_response_size=65536,
            )
        except RuntimeError as error:
            print(f"Markets retry after {parameters}: {error}")
    return {}


def fetch_events() -> dict[str, Any]:
    parameter_sets = [
        {"limit": 30, "order": "volume", "ascending": False, "active": True, "closed": False},
        {"limit": 30, "order": "createdAt", "ascending": False, "active": True},
        {"limit": 30, "active": True},
        {"limit": 30},
    ]
    for parameters in parameter_sets:
        try:
            return execute_tool(
                EVENTS_TOOL_ID,
                SESSION_ID,
                parameters,
                max_response_size=65536,
            )
        except RuntimeError as error:
            print(f"Events retry after {parameters}: {error}")
    return {}


def main() -> dict[str, Any]:
    try:
        volume_payload = fetch_volume()
    except RuntimeError as error:
        print(f"Volume unavailable: {error}")
        volume_payload = {}
    open_interest_payload = fetch_open_interest()
    series_payload = fetch_series()
    markets_payload = fetch_markets()
    events_payload = fetch_events()

    volume_series = extract_volume_series(volume_payload)
    open_interest_total, top_markets = extract_open_interest(open_interest_payload)
    market_candidates = (
        extract_market_rows(markets_payload)
        or extract_market_rows(events_payload)
        or top_markets
    )
    top_themes = (
        extract_theme_rows(series_payload)
        or extract_theme_rows(events_payload)
        or extract_theme_rows(markets_payload)
    )
    if not volume_series and open_interest_total <= 0:
        raise RuntimeError(
            "QVeris returned no usable Polymarket volume or open-interest rows."
        )

    if not volume_series:
        volume_series = [{"date": "open interest snapshot", "volume": open_interest_total}]

    current_volume = volume_series[-1]["volume"]
    previous_volume = volume_series[-2]["volume"] if len(volume_series) > 1 else current_volume
    volume_change = pct_change(current_volume, previous_volume)
    label = activity_label(volume_change)

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
        "top_themes": top_themes,
        "top_markets": market_candidates,
        "volume_series": volume_series,
        "volume_available": bool(volume_payload),
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
