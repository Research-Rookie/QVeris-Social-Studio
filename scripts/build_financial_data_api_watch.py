"""Build a Financial Data API Watch dataset from existing QVeris outputs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT_DIR = Path(__file__).resolve().parent.parent
FCF_FILE = ROOT_DIR / "data" / "fcf_yield.json"
NEWS_FILE = ROOT_DIR / "data" / "financial_news_signal.json"
OUTPUT_FILE = ROOT_DIR / "data" / "financial_data_api_watch.json"
RUN_TIMEZONE = ZoneInfo("Asia/Shanghai")


def money_billions(value: float) -> str:
    if value >= 1_000_000_000_000:
        return f"${value / 1_000_000_000_000:.1f}T"
    return f"${value / 1_000_000_000:.1f}B"


def pct(value: float) -> str:
    return f"{value:.1f}%"


def short_text(value: object, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def load_json(path: Path) -> dict:
    if not path.exists():
        raise RuntimeError(f"Missing required input file: {path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> dict:
    fcf = load_json(FCF_FILE)
    news = load_json(NEWS_FILE)
    companies = fcf.get("companies") or []
    if len(companies) < 2:
        raise RuntimeError("FCF dataset must contain at least two companies.")

    companies = sorted(companies, key=lambda item: item.get("latest_fcf_yield", 0), reverse=True)
    left, right = companies[0], companies[1]
    top_news = (news.get("signal_articles") or news.get("articles") or [{}])[0]
    top_ticker = news.get("top_ticker") or "Market"
    top_theme = news.get("top_topic") or "Financial Markets"
    tone = news.get("dominant_sentiment") or "Neutral"

    task = f"Compare ${left['symbol']} vs ${right['symbol']} using valuation and live news signals"
    retrieved = [
        {
            "label": "Free cash flow",
            "value": f"{left['symbol']} {money_billions(left.get('latest_ttm_fcf', 0))}",
        },
        {
            "label": "Market cap",
            "value": f"{left['symbol']} {money_billions(left.get('market_cap', 0))}",
        },
        {
            "label": "FCF yield",
            "value": f"{left['symbol']} {pct(left.get('latest_fcf_yield', 0))}",
        },
        {
            "label": "News signal",
            "value": f"{top_ticker} / {tone}",
        },
    ]

    takeaway = (
        f"QVeris turns scattered financial APIs into one agent workflow: "
        f"{left['symbol']} screens at {pct(left.get('latest_fcf_yield', 0))} FCF yield, "
        f"while current news attention is centered on {top_ticker}."
    )

    now = datetime.now(timezone.utc)
    run_now = datetime.now(RUN_TIMEZONE)
    output = {
        "updated_at": now.isoformat(),
        "date": run_now.strftime("%Y-%m-%d"),
        "run_timezone": "Asia/Shanghai",
        "source": "QVeris API via valuation and news capabilities",
        "title": "Financial Data API Watch",
        "scenario": "Valuation + News Check",
        "agent_task": task,
        "symbols": [left["symbol"], right["symbol"]],
        "companies": companies[:2],
        "capabilities": [
            "Financial fundamentals",
            "Market capitalization",
            "Free cash flow yield",
            "Financial news",
            "News sentiment",
        ],
        "retrieved": retrieved,
        "news": {
            "top_ticker": top_ticker,
            "top_theme": top_theme,
            "tone": tone,
            "lead_story": short_text(top_news.get("title", "Market headline pending"), 110),
            "source": top_news.get("source", "QVeris"),
        },
        "takeaway": takeaway,
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {OUTPUT_FILE}")
    print(task)
    return output


if __name__ == "__main__":
    main()
