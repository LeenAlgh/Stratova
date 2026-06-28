"""Report section cards and key findings."""

import html

import streamlit as st

from ui.report_parser import ParsedReport, ReportSection


def render_executive_summary(title: str, body: str) -> None:
    st.markdown(
        f"""
        <div class="section-card">
            <div class="section-card-header">📄 {html.escape(title)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(body)


def render_key_findings(findings: list[dict[str, str]]) -> None:
    if not findings:
        return

    st.markdown(
        '<div class="section-card"><div class="section-card-header">⚡ Key Findings</div></div>',
        unsafe_allow_html=True,
    )

    cards_html = '<div class="findings-list">'
    for idx, finding in enumerate(findings, start=1):
        priority = "HIGH" if idx <= 2 else "MEDIUM"
        badge_class = "priority-high" if priority == "HIGH" else "priority-medium"
        cards_html += f"""
        <div class="finding-card">
            <div class="finding-number">{idx}</div>
            <div class="finding-content">
                <div class="finding-header">
                    <span class="finding-title">{html.escape(finding.get("title", "Finding"))}</span>
                    <span class="priority-badge {badge_class}">{priority}</span>
                </div>
                <p class="finding-body">{html.escape(finding.get("body", ""))}</p>
            </div>
        </div>
        """
    cards_html += "</div>"
    st.markdown(cards_html, unsafe_allow_html=True)


def render_report_sections(report: ParsedReport) -> None:
    for section in report.sections:
        render_section_expander(section)


def render_section_expander(section: ReportSection) -> None:
    with st.expander(section.title, expanded=False):
        st.markdown(section.body)


def render_markdown_sections(sections: list[tuple[str, str]]) -> None:
    for title, body in sections:
        with st.expander(title, expanded=False):
            st.markdown(body)
