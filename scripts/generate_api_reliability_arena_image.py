"""Render the API Reliability Arena card as a 1200x675 PNG."""

from __future__ import annotations

import base64
import html
import json
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT_DIR / "data" / "api_reliability_arena.json"
TEMPLATE_FILE = ROOT_DIR / "scripts" / "templates" / "api_reliability_arena_template.html"
LOGO_FILE = ROOT_DIR / "scripts" / "templates" / "logo-color.avif"
OUTPUT_DIR = ROOT_DIR / "images"


def short(value: object, limit: int) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."


def metric(value: object, formatter, suffix: str) -> tuple[str, str]:
    if value is None:
        return "n/a", "not returned"
    return formatter(float(value)), suffix


def rows(items: list[dict]) -> str:
    rendered = []
    for item in items[:3]:
        success, success_note = metric(item.get("success_rate"), lambda value: f"{value * 100:.1f}%", "historical")
        latency, latency_note = metric(item.get("latency_ms"), lambda value: f"{value:,.0f} ms", "average")
        cost, cost_note = metric(item.get("cost_credits"), lambda value: f"{value:g} cr", "expected")
        score = float(item.get("route_score") or 0)
        champion = " champion" if int(item.get("rank") or 0) == 1 else ""
        rendered.append(
            f'<div class="row{champion}">'
            f'<div class="rank">{int(item.get("rank") or 0)}</div>'
            f'<div class="identity"><strong>{html.escape(short(item.get("name"), 42))}</strong><span>{html.escape(short(item.get("provider"), 42))}</span></div>'
            f'<div class="metric success"><strong>{html.escape(success)}</strong><span>{success_note}</span></div>'
            f'<div class="metric"><strong>{html.escape(latency)}</strong><span>{latency_note}</span></div>'
            f'<div class="metric"><strong>{html.escape(cost)}</strong><span>{cost_note}</span></div>'
            f'<div class="metric score"><strong>{score:.1f}</strong><div class="scoreTrack"><div class="scoreFill" style="width:{max(4,min(score,100)):.1f}%"></div></div></div>'
            "</div>"
        )
    return "".join(rendered)


def render(data: dict) -> str:
    page = TEMPLATE_FILE.read_text(encoding="utf-8")
    values = {
        "{{DATE}}": data.get("date", ""),
        "{{TASK}}": short((data.get("scenario") or {}).get("task", "Finance capability routing"), 94),
        "{{ROWS}}": rows(data.get("competitors") or []),
        "{{TAKEAWAY}}": short(data.get("takeaway", ""), 155),
        "{{LOGO}}": "data:image/avif;base64," + base64.b64encode(LOGO_FILE.read_bytes()).decode("ascii"),
    }
    for token, value in values.items():
        page = page.replace(token, str(value) if token in {"{{ROWS}}", "{{LOGO}}"} else html.escape(str(value)))
    return page


def main() -> None:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8-sig"))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    scenario_key = (data.get("scenario") or {}).get("key", "finance")
    dated = OUTPUT_DIR / f"api_reliability_arena_{scenario_key}_{data['date']}.png"
    latest = OUTPUT_DIR / "api_reliability_arena_latest.png"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1200, "height": 675}, device_scale_factor=1)
        page.set_content(render(data), wait_until="networkidle")
        page.screenshot(path=str(dated))
        browser.close()
    latest.write_bytes(dated.read_bytes())
    print(f"Saved {dated}")


if __name__ == "__main__":
    main()
