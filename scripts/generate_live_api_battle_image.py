"""Render the Live API Battle card as a 1200x675 PNG."""

from __future__ import annotations

import base64
import html
import json
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT_DIR / "data" / "live_api_battle.json"
TEMPLATE_FILE = ROOT_DIR / "scripts" / "templates" / "live_api_battle_template.html"
LOGO_FILE = ROOT_DIR / "scripts" / "templates" / "logo-color.avif"
OUTPUT_DIR = ROOT_DIR / "images"


def short(value: object, limit: int) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."


def format_price(value: object) -> str:
    return "n/a" if value is None else f"${float(value):,.2f}"


def format_change(value: object) -> str:
    return "change n/a" if value is None else f"{float(value):+.2f}%"


def rows(items: list[dict]) -> str:
    rendered = []
    for item in items[:3]:
        is_winner = int(item.get("rank") or 0) == 1
        status = "winner" if is_winner else ""
        score = float(item.get("battle_score") or 0)
        completeness = float(item.get("completeness") or 0) * 100
        latency = f"{int(item.get('latency_ms') or 0):,} ms" if item.get("success") else "Failed"
        rendered.append(
            f'<div class="battleRow {status}">'
            f'<div class="rank">{int(item.get("rank") or 0)}</div>'
            f'<div class="provider"><strong>{html.escape(short(item.get("provider"), 31))}</strong>'
            f'<span>{html.escape(short(item.get("name"), 48))}</span></div>'
            f'<div class="quote"><strong>{format_price(item.get("price"))}</strong>'
            f'<span>{format_change(item.get("change_pct"))}</span></div>'
            f'<div class="metric"><strong>{latency}</strong><span>live response</span></div>'
            f'<div class="metric"><strong>{completeness:.0f}%</strong><span>fields returned</span></div>'
            f'<div class="metric"><strong>{html.escape(str(item.get("freshness_label") or "n/a"))}</strong>'
            f'<span>{html.escape(str(item.get("cost_label") or "Cost n/a"))}</span></div>'
            f'<div class="score"><strong>{score:.1f}</strong><div><i style="width:{max(2, min(score, 100)):.1f}%"></i></div></div>'
            '</div>'
        )
    return "".join(rendered)


def render(data: dict) -> str:
    winner = data.get("winner") or {}
    replacements = {
        "{{DATE}}": html.escape(str(data.get("date") or "")),
        "{{QUESTION}}": html.escape(short(data.get("question"), 76)),
        "{{ROWS}}": rows(data.get("participants") or []),
        "{{WINNER}}": html.escape(short(winner.get("provider"), 36)),
        "{{REASON}}": html.escape(short(data.get("winner_reason"), 125)),
        "{{LOGO}}": "data:image/avif;base64," + base64.b64encode(LOGO_FILE.read_bytes()).decode("ascii"),
    }
    page = TEMPLATE_FILE.read_text(encoding="utf-8")
    for token, value in replacements.items():
        page = page.replace(token, value)
    return page


def main() -> None:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8-sig"))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    symbol = str((data.get("scenario") or {}).get("symbol") or "market").lower()
    dated = OUTPUT_DIR / f"live_api_battle_{symbol}_{data['date']}.png"
    latest = OUTPUT_DIR / "live_api_battle_latest.png"
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
