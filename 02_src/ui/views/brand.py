"""Brand Alignment read-only view for the Dashboard."""

import httpx
import streamlit as st

from ui.agent_data import load_local_json, load_local_text
from ui.api_client import StratovaAPI
from ui.run_loader import load_agent_ui
from ui.utils.brand_alignment import (
    PAGE_SUBTITLE,
    PAGE_TITLE,
    render_brand_alignment_page,
)


def _load_brand_legacy(api: StratovaAPI, company: str) -> tuple[dict | None, str | None]:
    try:
        return api.get_brand_json(company), None
    except httpx.HTTPError:
        pass

    local = load_local_json("brand", company)
    if local:
        return local, None

    local_txt = load_local_text("brand", company)
    if local_txt:
        return None, local_txt

    return None, None


def render(api: StratovaAPI, company: str, client_config: dict, reports: dict) -> None:
    ui_data = load_agent_ui("brand")
    if ui_data:
        render_brand_alignment_page(ui_data)
        return

    brand_data, text_fallback = _load_brand_legacy(api, company)
    if brand_data:
        render_brand_alignment_page(brand_data)
        return

    if text_fallback:
        st.markdown(
            f'<div class="hero-card"><h2 class="hero-title">{PAGE_TITLE}</h2>'
            f'<p class="hero-subtitle">{PAGE_SUBTITLE}</p></div>',
            unsafe_allow_html=True,
        )
        st.text(text_fallback)
        return

    st.markdown(
        f'<div class="hero-card"><h2 class="hero-title">{PAGE_TITLE}</h2>'
        f'<p class="hero-subtitle">{PAGE_SUBTITLE}</p>'
        f'<p class="hero-subtitle">● Not started</p></div>',
        unsafe_allow_html=True,
    )
    st.info("No brand alignment output in the latest run. Start a **New Run** to generate results.")
