"""Render World Cup finance signal card as a 1200x675 PNG."""

from __future__ import annotations

import base64
import html
import json
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT_DIR = Path(__file__).resolve().parent.parent
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_FILE = ROOT_DIR / "data" / "world_cup_finance.json"
TEMPLATE_FILE = SCRIPT_DIR / "templates" / "world_cup_finance_template.html"
LOGO_FILE = SCRIPT_DIR / "templates" / "logo-color.avif"
OUTPUT_DIR = ROOT_DIR / "images"
WIDTH, HEIGHT = 1200, 675


def get_logo_data_url() -> str:
    logo = base64.b64encode(LOGO_FILE.read_bytes()).decode("ascii")
    return f"data:image/avif;base64,{logo}"


def pct(value: float) -> str:
    return f"{value:+.2f}%"


def build_rows(stocks: list[dict]) -> str:
    rows = []
    max_abs = max(abs(stock["change_pct"]) for stock in stocks[:8]) or 1
    for stock in stocks[:8]:
        positive = stock["change_pct"] >= 0
        bar_width = max(6, min(100, abs(stock["change_pct"]) / max_abs * 100))
        rows.append(
            f"""
            <div class="stock-row">
              <div class="stock-main">
                <span class="ticker">${html.escape(stock['symbol'])}</span>
                <span class="company">{html.escape(stock['company'])}</span>
              </div>
              <div class="bar-track">
                <div class="bar {'up' if positive else 'down'}" style="width:{bar_width:.1f}%"></div>
              </div>
              <div class="move {'up-text' if positive else 'down-text'}">{pct(stock['change_pct'])}</div>
              <div class="theme">{html.escape(stock['theme'])}</div>
            </div>
            """
        )
    return "\n".join(rows)


def render_html(data: dict) -> str:
    stocks = data["stocks"]
    leader = data["leader"]
    top_theme = data["top_theme"]
    template = TEMPLATE_FILE.read_text(encoding="utf-8")
    return (
        template.replace("{{DATE}}", html.escape(data["date"]))
        .replace("{{MATCH}}", html.escape(data["match_label"]))
        .replace("{{LEADER}}", html.escape(f"${leader['symbol']} {pct(leader['change_pct'])}"))
        .replace("{{THEME}}", html.escape(f"{top_theme['name']} {pct(top_theme['avg_change_pct'])} avg"))
        .replace("{{ROWS}}", build_rows(stocks))
        .replace("{{LOGO}}", get_logo_data_url())
    )


def render_to_png(html_text: str, output_path: Path) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(
            viewport={"width": WIDTH, "height": HEIGHT},
            device_scale_factor=1,
        )
        page.set_content(html_text, wait_until="networkidle")
        page.screenshot(path=str(output_path))
        browser.close()


def main() -> None:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    html_text = render_html(data)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    dated_path = OUTPUT_DIR / f"world_cup_finance_{data['date']}.png"
    latest_path = OUTPUT_DIR / "world_cup_finance_latest.png"

    render_to_png(html_text, dated_path)
    latest_path.write_bytes(dated_path.read_bytes())

    print(f"Saved {dated_path}")
    print(f"Saved {latest_path}")


if __name__ == "__main__":
    main()
