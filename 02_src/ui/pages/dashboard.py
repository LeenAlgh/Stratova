"""Dashboard — read-only viewer for latest ORCA run outputs."""

import streamlit as st

from ui.api_client import StratovaAPI
from ui.components.header import render_header
from ui.run_loader import load_latest_run, reports_from_latest_run
from ui.views import analysis, brand, content, research, strategy

DEFAULT_COMPANY = "Beam Data"

AGENT_TABS = [
    ("research", "Research"),
    ("strategy", "Strategy"),
    ("content", "Content"),
    ("brand", "Brand Alignment"),
    ("analysis", "Analysis"),
]

_VIEW_RENDERERS = {
    "research": research.render,
    "strategy": strategy.render,
    "content": content.render,
    "brand": brand.render,
    "analysis": analysis.render,
}


def render(api: StratovaAPI) -> None:
    st.markdown(
        """
        <style>
        section.main div.block-container {
            padding-left: 1rem !important;
            padding-right: 1rem !important;
            max-width: 1200px !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    render_header(api)

    latest = load_latest_run()
    reports = reports_from_latest_run()

    if latest:
        run_id = latest.get("run_id", "—")
        updated = latest.get("updated_at", "—")
        st.caption(f"Latest run: `{run_id}` · updated {updated}")
    else:
        st.caption("No ORCA run loaded yet.")

    if not any(reports.values()):
        st.markdown(
            """
            <div class="hero-card hero-card-muted">
                <h2 class="hero-title">Stratova Dashboard</h2>
                <p class="hero-subtitle">No pipeline outputs yet.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.info("Go to **New Run** to describe your product, market, and audience, then start the ORCA pipeline.")
        st.markdown(
            '<p class="dashboard-footer">Read-only viewer • displays ORCA outputs. '
            "Does not run agents or modify data.</p>",
            unsafe_allow_html=True,
        )
        return

    tab_labels = [label for _, label in AGENT_TABS]
    st.markdown('<div class="dashboard-tabs-anchor"></div>', unsafe_allow_html=True)
    tabs = st.tabs(tab_labels)
    company = DEFAULT_COMPANY
    empty_config: dict = {}

    for tab_container, (agent_id, _) in zip(tabs, AGENT_TABS):
        with tab_container:
            renderer = _VIEW_RENDERERS[agent_id]
            renderer(api, company, empty_config, reports)

    st.markdown(
        '<p class="dashboard-footer">Read-only viewer • displays ORCA outputs. '
        "Does not run agents or modify data.</p>",
        unsafe_allow_html=True,
    )
