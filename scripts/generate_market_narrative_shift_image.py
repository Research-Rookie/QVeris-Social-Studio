"""Render the Market Narrative Shift card as a 1200x675 PNG."""

from __future__ import annotations

import base64
import html
import json
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT_DIR / "data" / "market_narrative_shift.json"
TEMPLATE_FILE = ROOT_DIR / "scripts" / "templates" / "market_narrative_shift_template.html"
LOGO_FILE = ROOT_DIR / "scripts" / "templates" / "logo-color.avif"
OUTPUT_DIR = ROOT_DIR / "images"
WIDTH, HEIGHT = 1200, 675


def short_text(value: object, limit: int) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."


def logo_data_url() -> str:
    return "data:image/avif;base64," + base64.b64encode(LOGO_FILE.read_bytes()).decode("ascii")


def term_rows(terms: list[str], empty: str) -> str:
    values = terms[:3] or [empty]
    return "".join(f"<li>{html.escape(short_text(value, 28))}</li>" for value in values)


def score_label(score: float) -> str:
    if score >= 0.35:
        return "Bullish"
    if score >= 0.15:
        return "Leaning bullish"
    if score <= -0.35:
        return "Bearish"
    if score <= -0.15:
        return "Leaning bearish"
    return "Neutral"


def render_html(data: dict) -> str:
    template = TEMPLATE_FILE.read_text(encoding="utf-8")
    current = data.get("current") or {}
    previous = data.get("previous") or {}
    sentiment_delta = float(data.get("sentiment_delta") or 0.0)
    delta_class = "positive" if sentiment_delta > 0.015 else "negative" if sentiment_delta < -0.015 else "neutral"
    replacements = {
        "{{DATE}}": data.get("date", ""),
        "{{SYMBOL}}": data.get("symbol", "Market"),
        "{{SHIFT}}": data.get("shift_label", "Narrative steady"),
        "{{CURRENT_TONE}}": score_label(float(current.get("sentiment_score") or 0.0)),
        "{{CURRENT_SCORE}}": f"{float(current.get('sentiment_score') or 0.0):+.2f}",
        "{{PREVIOUS_SCORE}}": f"{float(previous.get('sentiment_score') or 0.0):+.2f}" if previous else "n/a",
        "{{DELTA}}": f"{sentiment_delta:+.2f}" if previous else "new",
        "{{DELTA_CLASS}}": delta_class,
        "{{CURRENT_THEME}}": short_text(current.get("top_theme", "Financial Markets"), 30),
        "{{PREVIOUS_THEME}}": short_text(previous.get("top_theme", "Baseline building"), 30),
        "{{CURRENT_COUNT}}": str(current.get("article_count", 0)),
        "{{PREVIOUS_COUNT}}": str(previous.get("article_count", 0)) if previous else "n/a",
        "{{BASELINE}}": data.get("baseline_label", "Building"),
        "{{TAKEAWAY}}": short_text(data.get("takeaway", ""), 210),
        "{{HEADLINE}}": short_text(current.get("headline", "Market headline pending"), 112),
        "{{SOURCE}}": short_text(current.get("headline_source", "QVeris"), 30),
        "{{EMERGING}}": term_rows(data.get("emerging_keywords") or data.get("emerging_themes") or [], "Baseline building"),
        "{{FADING}}": term_rows(data.get("fading_keywords") or data.get("fading_themes") or [], "No fading theme yet"),
        "{{LOGO}}": logo_data_url(),
    }
    for token, value in replacements.items():
        template = template.replace(token, html.escape(str(value)) if token not in {"{{EMERGING}}", "{{FADING}}", "{{LOGO}}"} else str(value))
    return template


def render_to_png(html_text: str, output_path: Path) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": WIDTH, "height": HEIGHT}, device_scale_factor=1)
        page.set_content(html_text, wait_until="networkidle")
        page.screenshot(path=str(output_path))
        browser.close()


def main() -> None:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8-sig"))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    dated_path = OUTPUT_DIR / f"market_narrative_shift_{data['symbol']}_{data['date']}.png"
    latest_path = OUTPUT_DIR / "market_narrative_shift_latest.png"
    render_to_png(render_html(data), dated_path)
    latest_path.write_bytes(dated_path.read_bytes())
    print(f"Saved {dated_path}")
    print(f"Saved {latest_path}")


if __name__ == "__main__":
    main()
