"""Analysis Agent read-only view for the Dashboard."""

import streamlit as st

from ui.api_client import StratovaAPI
from ui.run_loader import load_agent_ui, load_latest_run
from ui.utils.analysis_render import (
    PAGE_SUBTITLE,
    PAGE_TITLE,
    load_analysis_ui,
    render_analysis_page,
)


def render(api: StratovaAPI, company: str, client_config: dict, reports: dict) -> None:
    ui_data = load_agent_ui("analysis")
    if not ui_data:
        latest = load_latest_run()
        run_id = latest.get("run_id") if latest else None
        if run_id:
            ui_data = load_analysis_ui(run_id)

    if ui_data:
        render_analysis_page(ui_data)
        return

    st.markdown(
        f'<div class="hero-card"><h2 class="hero-title">{PAGE_TITLE}</h2>'
        f'<p class="hero-subtitle">{PAGE_SUBTITLE}</p>'
        f'<p class="hero-subtitle">● Not started</p></div>',
        unsafe_allow_html=True,
    )
    st.info("No analysis output in the latest run. Start a **New Run** to generate results.")
