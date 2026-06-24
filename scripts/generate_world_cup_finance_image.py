"""Render one World Cup ETF card per finished match."""

from __future__ import annotations

import base64
import html
import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT_DIR = Path(__file__).resolve().parent.parent
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_FILE = ROOT_DIR / "data" / "world_cup_finance.json"
TEMPLATE_FILE = SCRIPT_DIR / "templates" / "world_cup_etf_template.html"
LOGO_FILE = SCRIPT_DIR / "templates" / "logo-color.avif"
OUTPUT_DIR = ROOT_DIR / "images"
WIDTH, HEIGHT = 1200, 675


def get_logo_data_url() -> str:
    logo = base64.b64encode(LOGO_FILE.read_bytes()).decode("ascii")
    return f"data:image/avif;base64,{logo}"


def pct(value: float) -> str:
    return f"{value:+.2f}%"


def money(value: float) -> str:
    return f"${value:,.2f}"


def safe_slug(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "match"


def match_slug(match: dict, date: str) -> str:
    return safe_slug(f"{date}-{match['id']}-{match['home']['team']}-{match['away']['team']}")


def bar_width(home_pct: float, away_pct: float, current_pct: float) -> float:
    max_abs = max(abs(home_pct), abs(away_pct), 0.5)
    return max(8, min(100, abs(current_pct) / max_abs * 100))


def result_text(match: dict) -> str:
    home = match["home"]
    away = match["away"]
    result = match.get("result")
    if result == "draw":
        return "Draw: attention splits between both markets"
    if result == "home_win":
        return f"{home['team']} win: watch {home['etf']} vs {away['etf']}"
    if result == "away_win":
        return f"{away['team']} win: watch {away['etf']} vs {home['etf']}"
    return "Final result linked to ETF watchlist"


def side_block(side: dict, other_pct: float) -> str:
    quote = side["quote"]
    change_pct = float(quote.get("change_pct", 0))
    is_up = change_pct >= 0
    width = bar_width(change_pct, other_pct, change_pct)
    proxy_badge = '<span class="proxy-badge">Proxy ETF</span>' if side.get("is_proxy") else ""
    proxy_note = side.get("proxy_note") or ""
    note = f'<div class="proxy-note">{html.escape(proxy_note)}</div>' if proxy_note else ""
    return f"""
      <section class="team-card">
        <div class="team-name">{html.escape(side['team'])}{proxy_badge}</div>
        <div class="score">{html.escape(str(side.get('score', '-')))}</div>
        <div class="etf">${html.escape(side['etf'])}</div>
        <div class="etf-name">{html.escape(side.get('etf_name', side['etf']))}</div>
        {note}
        <div class="price">{money(float(quote.get('price', 0)))}</div>
        <div class="move {'up' if is_up else 'down'}">{pct(change_pct)}</div>
        <div class="bar-wrap">
          <div class="bar {'bar-up' if is_up else 'bar-down'}" style="width:{width:.1f}%"></div>
        </div>
      </section>
    """


def render_html(data: dict, match: dict) -> str:
    home_pct = float(match["home"]["quote"].get("change_pct", 0))
    away_pct = float(match["away"]["quote"].get("change_pct", 0))
    template = TEMPLATE_FILE.read_text(encoding="utf-8")
    return (
        template.replace("{{DATE}}", html.escape(data["date"]))
        .replace("{{EVENT}}", html.escape(data.get("event", "World Cup")))
        .replace("{{MATCH}}", html.escape(match["label"]))
        .replace("{{RESULT_TEXT}}", html.escape(result_text(match)))
        .replace("{{HOME_CARD}}", side_block(match["home"], away_pct))
        .replace("{{AWAY_CARD}}", side_block(match["away"], home_pct))
        .replace("{{SOURCE}}", html.escape(data.get("source", "QVeris API")))
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
    matches = data.get("matches") or []
    if not matches:
        print("No finished mapped World Cup matches. Skipping image generation.")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for index, match in enumerate(matches):
        slug = match_slug(match, data["date"])
        output_path = OUTPUT_DIR / f"world_cup_etf_{slug}.png"
        html_text = render_html(data, match)
        render_to_png(html_text, output_path)
        print(f"Saved {output_path}")
        if index == 0:
            latest_path = OUTPUT_DIR / "world_cup_etf_latest.png"
            latest_path.write_bytes(output_path.read_bytes())
            print(f"Saved {latest_path}")


if __name__ == "__main__":
    main()
