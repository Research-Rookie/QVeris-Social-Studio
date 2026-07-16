"""Render Earnings Reality Check as a 1200x675 PNG."""

from __future__ import annotations

import base64
import html
import json
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT_DIR / "data" / "earnings_reality_check.json"
TEMPLATE_FILE = ROOT_DIR / "scripts" / "templates" / "earnings_reality_check_template.html"
LOGO_FILE = ROOT_DIR / "scripts" / "templates" / "logo-color.avif"
OUTPUT_DIR = ROOT_DIR / "images"


def short(value: object, limit: int) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."


def render(data: dict) -> str:
    reaction = data.get("price_reaction") or {}
    actual = float(data.get("actual_eps") or 0)
    estimate = float(data.get("estimated_eps") or 0)
    maximum = max(abs(actual), abs(estimate), 0.01)
    surprise = float(data.get("surprise_pct") or 0)
    move = float(reaction.get("change_pct") or 0)
    accent = "#50e0c1" if surprise >= 0 else "#ff6d68"
    values = {
        "{{DATE}}": data.get("date", ""),
        "{{SYMBOL}}": data.get("symbol", ""),
        "{{COMPANY}}": data.get("company", ""),
        "{{REPORT_DATE}}": data.get("reported_date", ""),
        "{{REPORT_TIME}}": short(data.get("report_time", ""), 24).replace("-", " ").title(),
        "{{ACTUAL_EPS}}": f"{actual:.2f}",
        "{{ESTIMATED_EPS}}": f"{estimate:.2f}",
        "{{SURPRISE_PCT}}": f"{surprise:+.1f}%",
        "{{VERDICT}}": data.get("verdict", "Mixed reaction"),
        "{{TAKEAWAY}}": short(data.get("takeaway", ""), 165),
        "{{PRICE_REACTION}}": f"{move:+.2f}%" if reaction.get("available") else "Pending",
        "{{REACTION_WINDOW}}": f"{reaction.get('base_date')} → {reaction.get('reaction_date')}" if reaction.get("available") else "Waiting for next close",
        "{{ESTIMATE_WIDTH}}": f"{max(12, abs(estimate) / maximum * 100):.1f}",
        "{{ACTUAL_WIDTH}}": f"{max(12, abs(actual) / maximum * 100):.1f}",
        "{{ACCENT}}": accent,
        "{{LOGO}}": "data:image/avif;base64," + base64.b64encode(LOGO_FILE.read_bytes()).decode("ascii"),
    }
    page = TEMPLATE_FILE.read_text(encoding="utf-8")
    for token, value in values.items():
        page = page.replace(token, str(value) if token in {"{{ACCENT}}", "{{ESTIMATE_WIDTH}}", "{{ACTUAL_WIDTH}}", "{{LOGO}}"} else html.escape(str(value)))
    return page


def main() -> None:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8-sig"))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"earnings_reality_check_{data['symbol']}_{data['reported_date']}.png"
    dated = OUTPUT_DIR / filename
    latest = OUTPUT_DIR / "earnings_reality_check_latest.png"
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
