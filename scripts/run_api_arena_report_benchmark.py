"""Run reproducible five-prompt benchmarks for API Arena and Live API Battle.

The script is intentionally separate from the daily card pipelines. It writes
report-oriented JSON files and does not modify posts.json or website images.
"""

from __future__ import annotations

import argparse
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from fetch_api_reliability_arena import SCENARIOS, normalize_tool
from fetch_live_api_battle import (
    SESSION_ID as BATTLE_SESSION_ID,
    SYMBOLS,
    run_candidate,
    score_results,
    unique_candidates,
)
from qveris_finance import search_tools


ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT_DIR / "benchmark-results"
RUN_TIMEZONE = ZoneInfo("Asia/Shanghai")


def arena_prompt(scenario: dict[str, str]) -> str:
    return scenario["query"]


def battle_prompt(symbol: str) -> str:
    return f"What is {symbol}'s latest U.S. stock quote?"


def battle_search_query(symbol: str) -> str:
    return (
        f"API endpoint to retrieve the latest U.S. stock quote for ticker {symbol}, including "
        "current price, percent change, trading volume, and timestamp; exclude market clock, "
        "calendar, exchange status, order book, and news tools"
    )


def run_arena() -> dict[str, Any]:
    tests: list[dict[str, Any]] = []
    for index, scenario in enumerate(SCENARIOS[:5], start=1):
        prompt = arena_prompt(scenario)
        session_id = f"qveris-report-arena-{scenario['key']}"
        search_id, results = search_tools(prompt, session_id, limit=10)
        competitors = [normalize_tool(tool) for tool in results if tool.get("tool_id")]
        competitors.sort(
            key=lambda item: (
                item["metric_count"],
                item["route_score"],
                item["success_rate"] or 0,
            ),
            reverse=True,
        )
        competitors = competitors[:3]
        for rank, competitor in enumerate(competitors, start=1):
            competitor["rank"] = rank
        tests.append(
            {
                "test_no": index,
                "scenario": scenario,
                "prompt": prompt,
                "search_id": search_id,
                "discovered_count": len(results),
                "competitors": competitors,
                "winner": competitors[0] if competitors else None,
            }
        )
        winner = competitors[0] if competitors else {}
        print(
            f"Arena {index}/5 {scenario['label']}: "
            f"{winner.get('provider', 'no winner')} / {winner.get('name', 'no result')}"
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "QVeris Discover routing signals",
        "test_count": len(tests),
        "methodology": {
            "historical_success_weight": 0.55,
            "historical_latency_weight": 0.25,
            "expected_cost_weight": 0.20,
            "important_note": "This is a pre-call routing comparison, not a live load test.",
        },
        "tests": tests,
    }


def run_battle() -> dict[str, Any]:
    tests: list[dict[str, Any]] = []
    now_utc = datetime.now(timezone.utc)
    for index, scenario in enumerate(SYMBOLS[:5], start=1):
        symbol = scenario["symbol"]
        prompt = battle_prompt(symbol)
        query = battle_search_query(symbol)
        search_id, discovered = search_tools(query, BATTLE_SESSION_ID, limit=20)
        candidates = unique_candidates(discovered)
        attempted: list[dict[str, Any]] = []
        for candidate in candidates:
            result = run_candidate(candidate, search_id, symbol, now_utc)
            attempted.append(result)
            usable = [
                item
                for item in attempted
                if item.get("success") and item.get("completeness", 0) > 0
            ]
            if len(usable) >= 3:
                break

        usable = [
            item
            for item in attempted
            if item.get("success") and item.get("completeness", 0) > 0
        ]
        failures = [item for item in attempted if item not in usable]
        participants = (usable[:3] + failures[: max(0, 3 - len(usable))])[:3]
        participants = score_results(participants) if participants else []
        prices = [
            float(item["price"])
            for item in participants
            if item.get("price") not in (None, 0)
        ]
        spread_pct = None
        if len(prices) >= 2:
            spread_pct = (max(prices) - min(prices)) / statistics.median(prices) * 100
        tests.append(
            {
                "test_no": index,
                "scenario": scenario,
                "prompt": prompt,
                "discovery_prompt": query,
                "search_id": search_id,
                "discovered_count": len(discovered),
                "attempted_count": len(attempted),
                "participants": participants,
                "winner": participants[0] if participants else None,
                "price_spread_pct": round(spread_pct, 4) if spread_pct is not None else None,
            }
        )
        winner = participants[0] if participants else {}
        print(
            f"Battle {index}/5 {symbol}: {winner.get('provider', 'no winner')} "
            f"score={winner.get('battle_score', 'n/a')}"
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Live API calls through QVeris",
        "test_count": len(tests),
        "methodology": {
            "field_completeness_weight": 0.40,
            "live_latency_weight": 0.25,
            "freshness_weight": 0.15,
            "expected_cost_weight": 0.10,
            "cross_provider_price_agreement_weight": 0.10,
            "important_note": (
                "Scores describe performance for these quote prompts during this run; "
                "they are not universal provider rankings."
            ),
        },
        "tests": tests,
    }


def dry_run_plan() -> None:
    print("API Arena prompts:")
    for index, scenario in enumerate(SCENARIOS[:5], start=1):
        print(f"  {index}. {arena_prompt(scenario)}")
    print("Live API Battle prompts:")
    for index, scenario in enumerate(SYMBOLS[:5], start=1):
        print(f"  {index}. {battle_prompt(scenario['symbol'])}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.dry_run:
        dry_run_plan()
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    run_meta = {
        "run_date": datetime.now(RUN_TIMEZONE).strftime("%Y-%m-%d"),
        "run_timezone": "Asia/Shanghai",
    }
    arena = {**run_meta, **run_arena()}
    battle = {**run_meta, **run_battle()}
    arena_path = OUTPUT_DIR / "api_arena_benchmark.json"
    battle_path = OUTPUT_DIR / "api_battle_benchmark.json"
    arena_path.write_text(json.dumps(arena, ensure_ascii=False, indent=2), encoding="utf-8")
    battle_path.write_text(json.dumps(battle, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {arena_path}")
    print(f"Saved {battle_path}")


if __name__ == "__main__":
    main()
