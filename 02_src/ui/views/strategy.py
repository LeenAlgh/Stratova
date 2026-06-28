"""Strategy Agent read-only view for the Dashboard."""

import httpx
import streamlit as st

from ui.api_client import StratovaAPI
from ui.components.hero import render_hero
from ui.components.report_sections import (
    render_executive_summary,
    render_report_sections,
)
from ui.report_parser import parse_report_txt
from ui.run_loader import load_agent_ui
from ui.utils.metrics import (
    STRATEGY_METRIC_LABELS,
    derive_strategy_metrics,
    derive_ui_json_metrics,
)
from ui.utils.personas import render_personas_section
from ui.utils.strategy_render import render_strategy_sections

EMPTY_METRICS = {
    "icp_count": "—",
    "channels": "—",
    "time_to_market": "—",
}

STRATEGY_HERO_TITLE = "Strategy Agent"
STRATEGY_HERO_SUBTITLE = (
    "The Strategy Agent turns research into a clear Go-To-Market direction. "
    "It defines the ideal customer, positioning, messaging, channels, and action plan, "
    "helping businesses move from market insight to a focused, execution-ready strategy."
)
STRATEGY_HOW_IT_WORKS_TITLE = "How the Strategy Agent Works"
STRATEGY_HOW_IT_WORKS_BODY = """1. **Reviews the research foundation** — It starts by analyzing the market, audience, competitor, and opportunity insights produced by the Research Agent.

2. **Defines the ideal customer** — It identifies the best-fit customer profile and key buyer personas to focus the GTM strategy.

3. **Builds positioning** — It creates a clear positioning direction that explains where the product fits in the market and why it matters.

4. **Shapes messaging** — It develops messaging pillars that highlight the product's value, differentiation, and audience relevance.

5. **Selects strategic channels** — It recommends the most effective channels to reach, engage, and convert the target audience.

6. **Creates the GTM direction** — It combines the insights into a practical strategy with priorities, actions, metrics, and risks.

7. **Prepares the handoff** — It gives the Content Agent a clear strategic foundation to create aligned marketing assets."""


def _load_strategy_legacy(api: StratovaAPI, company: str) -> tuple[dict | None, str | None]:
    try:
        return api.get_strategy_json(company), None
    except httpx.HTTPError:
        pass
    try:
        text_payload = api.get_strategy_text(company)
        return None, text_payload.get("content")
    except httpx.HTTPError as exc:
        return None, str(exc)
    return None, None


def _legacy_sections(data: dict) -> list[dict[str, str]]:
    mapping = [
        ("Brand Alignment Foundation", ""),
        ("Strategy Assumptions", ""),
        ("ICP", "icp"),
        ("Personas", "personas"),
        ("Positioning", "positioning"),
        ("Messaging Pillars", "messaging_pillars"),
        ("Recommended Channels", "recommended_channels"),
        ("GTM Strategy", "gtm_strategy"),
        ("Metrics", ""),
        ("Risks and Mitigation", ""),
    ]
    sections: list[dict[str, str]] = []
    for title, key in mapping:
        body = data.get(key, "") if key else ""
        if body and str(body).strip():
            sections.append({"title": title, "body": str(body)})
    return sections


def _render_strategy_intro(status_badge: str, metrics: dict[str, str]) -> None:
    render_hero(
        STRATEGY_HERO_TITLE,
        STRATEGY_HERO_SUBTITLE,
        status_badge,
        metrics,
        metric_labels=STRATEGY_METRIC_LABELS,
    )
    render_executive_summary(STRATEGY_HOW_IT_WORKS_TITLE, STRATEGY_HOW_IT_WORKS_BODY)


def _render_ui_payload(data: dict) -> None:
    sections = data.get("sections") or []

    status = data.get("status", "completed")
    badge = "● Strategy Complete" if status == "completed" else f"● Strategy {status.title()}"
    _render_strategy_intro(badge, derive_ui_json_metrics("strategy", data))

    render_personas_section(data)
    render_strategy_sections(sections)


def render(api: StratovaAPI, company: str, client_config: dict, reports: dict) -> None:
    ui_data = load_agent_ui("strategy")
    if ui_data:
        _render_ui_payload(ui_data)
        return

    data, text_fallback = _load_strategy_legacy(api, company)
    if not data and not text_fallback:
        _render_strategy_intro("● Not started", EMPTY_METRICS)
        st.info("No strategy output in the latest run. Start a **New Run** to generate results.")
        return

    if data:
        _render_strategy_intro("● Strategy Complete", derive_strategy_metrics(data))

        render_personas_section({"personas": data.get("personas", "")})
        render_strategy_sections(_legacy_sections(data))
    elif text_fallback:
        report = parse_report_txt(text_fallback)
        _render_strategy_intro("● Strategy Complete", EMPTY_METRICS)
        render_report_sections(report)
