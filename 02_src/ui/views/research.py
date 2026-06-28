"""Research Agent read-only view for the Dashboard."""

import httpx
import streamlit as st

from ui.api_client import StratovaAPI
from ui.components.hero import render_hero
from ui.components.report_sections import (
    render_executive_summary,
    render_key_findings,
    render_markdown_sections,
    render_report_sections,
)
from ui.report_parser import parse_report_txt
from ui.run_loader import load_agent_ui
from ui.utils.markdown import extract_key_findings
from ui.utils.metrics import derive_research_metrics, derive_ui_json_metrics

RESEARCH_HERO_TITLE = "Research Agent"
RESEARCH_HERO_SUBTITLE = (
    "The Research Agent uncovers the market insights behind every winning Go-To-Market move. "
    "It analyzes the product, audience, competitors, trends, risks, and channels to give "
    "Stratova a strong foundation before strategy begins."
)
RESEARCH_HOW_IT_WORKS_TITLE = "How the Research Agent Works"
RESEARCH_HOW_IT_WORKS_BODY = """1. **Understands the opportunity** — It starts by identifying the product, market, and target audience behind the Go-To-Market request.

2. **Finds business context** — It gathers relevant company, product, and brand information to keep the research aligned with the business.

3. **Scans the market** — It looks at market trends, demand signals, opportunities, and risks that could shape the GTM direction.

4. **Studies the competition** — It reviews key competitors to understand positioning gaps, strengths, weaknesses, and differentiation opportunities.

5. **Identifies customer signals** — It highlights audience needs, pain points, buying triggers, and decision factors.

6. **Recommends high-potential channels** — It identifies the channels most likely to reach and convert the target audience.

7. **Delivers a research foundation** — It turns all findings into a clear GTM Research Summary that helps the Strategy Agent build a sharper, more market-ready plan."""

EMPTY_METRICS = {
    "sources": "—",
    "data_points": "—",
    "confidence": "—",
    "processing_time": "—",
}


def _load_research_legacy(api: StratovaAPI, company: str) -> tuple[dict | None, str | None]:
    try:
        return api.get_research_json(company), None
    except httpx.HTTPError:
        pass
    try:
        text_payload = api.get_research_text(company)
        return None, text_payload.get("content")
    except httpx.HTTPError as exc:
        return None, str(exc)
    return None, None


def _section_body(sections: list[dict], *title_keywords: str) -> str:
    for section in sections:
        title = (section.get("title") or "").lower()
        if any(kw.lower() in title for kw in title_keywords):
            return section.get("body") or ""
    return ""


def _render_research_intro(status_badge: str, metrics: dict[str, str]) -> None:
    render_hero(RESEARCH_HERO_TITLE, RESEARCH_HERO_SUBTITLE, status_badge, metrics)
    render_executive_summary(RESEARCH_HOW_IT_WORKS_TITLE, RESEARCH_HOW_IT_WORKS_BODY)


def _render_ui_payload(data: dict) -> None:
    sections = data.get("sections") or []

    status = data.get("status", "completed")
    badge = "● Research Complete" if status == "completed" else f"● Research {status.title()}"
    _render_research_intro(badge, derive_ui_json_metrics("research", data))

    findings_parts = [
        _section_body(sections, "opportunities"),
        _section_body(sections, "risks"),
    ]
    findings_text = "\n\n".join(part for part in findings_parts if part)
    render_key_findings(extract_key_findings(findings_text, limit=6))

    st.markdown('<div class="content-panel">', unsafe_allow_html=True)
    render_markdown_sections(
        [(s.get("title", "Section"), s.get("body", "")) for s in sections if s.get("body")]
    )
    st.markdown("</div>", unsafe_allow_html=True)


def render(api: StratovaAPI, company: str, client_config: dict, reports: dict) -> None:
    ui_data = load_agent_ui("research")
    if ui_data:
        _render_ui_payload(ui_data)
        return

    data, text_fallback = _load_research_legacy(api, company)
    if not data and not text_fallback:
        _render_research_intro("● Not started", EMPTY_METRICS)
        st.info("No research output in the latest run. Start a **New Run** to generate results.")
        return

    if data:
        _render_research_intro("● Research Complete", derive_research_metrics(data))

        combined = f"{data.get('market_research', '')}\n\n{data.get('competitor_analysis', '')}"
        render_key_findings(extract_key_findings(combined, limit=6))

        st.markdown('<div class="content-panel">', unsafe_allow_html=True)
        sections = [
            ("Market Scope", data.get("market_scope", "")),
            ("Market Research", data.get("market_research", "")),
            ("Competitor Analysis", data.get("competitor_analysis", "")),
            ("Marketing Channels", data.get("marketing_channels", "")),
        ]
        render_markdown_sections([(t, b) for t, b in sections if b])
        st.markdown("</div>", unsafe_allow_html=True)
    elif text_fallback:
        report = parse_report_txt(text_fallback)
        _render_research_intro(
            "● Research Complete",
            {"sources": "—", "data_points": str(len(report.sections)), "confidence": "—", "processing_time": "—"},
        )
        render_report_sections(report)
