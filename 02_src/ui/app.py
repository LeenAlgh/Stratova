"""Streamlit UI for Stratova GTM agents."""

import os
import sys
from pathlib import Path

import httpx
import streamlit as st

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from client_query import DEFAULT_GTM_BRIEF
from ui.api_client import DEFAULT_API_URL, StratovaAPI
from ui.config import LOGO_SVG_PATH, load_logo_svg
from ui.pages import dashboard, new_run

from project_paths import UI_STYLE_CSS


def _load_styles() -> None:
    st.markdown(
        f"<style>{UI_STYLE_CSS.read_text(encoding='utf-8')}</style>",
        unsafe_allow_html=True,
    )


def _get_api() -> StratovaAPI:
    return StratovaAPI(st.session_state.get("api_url", DEFAULT_API_URL))


def _render_sidebar_branding() -> None:
    logo = load_logo_svg()
    st.sidebar.markdown(
        f"""
        <div class="sidebar-brand">
            <div class="sidebar-logo">{logo}</div>
            <div>
                <div class="sidebar-title">Stratova</div>
                <div class="sidebar-subtitle">Multi-Agent GTM</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def run() -> None:
    st.set_page_config(
        page_title="Stratova",
        page_icon=str(LOGO_SVG_PATH),
        layout="wide",
    )
    _load_styles()
    _render_sidebar_branding()

    api = _get_api()

    try:
        defaults = api.get_default_client()
    except httpx.HTTPError:
        defaults = DEFAULT_GTM_BRIEF.copy()
        st.sidebar.error("API unreachable — start FastAPI with `uvicorn api.main:app --reload`")

    def dashboard_page() -> None:
        dashboard.render(api)

    def new_run_page() -> None:
        new_run.render(api, defaults)

    pg = st.navigation(
        [
            st.Page(dashboard_page, title="Dashboard", icon=":material/dashboard:"),
            st.Page(new_run_page, title="New Run", icon=":material/add_circle:"),
        ]
    )
    pg.run()


if __name__ == "__main__":
    run()
