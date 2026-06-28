"""New Run — GTM brief form and ORCA pipeline trigger."""

import httpx
import streamlit as st

from client_query import (
    DEFAULT_GTM_BRIEF,
    build_user_input_from_config,
    validate_gtm_brief,
)
from ui.api_client import StratovaAPI
from ui.components.run_controls import poll_orca_until_complete


def _init_brief_state(defaults: dict) -> None:
    if "gtm_brief" not in st.session_state:
        st.session_state.gtm_brief = defaults.copy()


def render(api: StratovaAPI, defaults: dict | None = None) -> None:
    defaults = defaults or DEFAULT_GTM_BRIEF
    st.markdown(
        """
        <style>
        section.main div.block-container {
            padding-left: clamp(2.5rem, 8vw, 7rem) !important;
            padding-right: clamp(2.5rem, 8vw, 7rem) !important;
            max-width: 100% !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    _init_brief_state(defaults)
    brief = st.session_state.gtm_brief

    st.title("New Run")
    st.markdown(
        "Describe the product, market, and audience. The brief is handed off to ORCA — "
        "the pipeline runs outside this dashboard and results appear on the **Dashboard** when complete."
    )

    brief["product"] = st.text_area(
        "Product *",
        value=brief.get("product", ""),
        height=120,
        placeholder=(
            "e.g. Lumora Pipeline Copilot — a revenue-intelligence module that auto-instruments "
            "CRM data and flags at-risk deals, from a mid-market RevOps platform."
        ),
        help="What are you launching? What does it do, and who makes it?",
    )

    brief["market"] = st.text_area(
        "Market",
        value=brief.get("market", ""),
        height=100,
        placeholder=(
            "e.g. Revenue intelligence / RevOps, North America, crowded with enterprise "
            "incumbents that require long implementations."
        ),
        help="Category, geography, and competitive context.",
    )

    brief["audience"] = st.text_area(
        "Audience *",
        value=brief.get("audience", ""),
        height=120,
        placeholder=(
            "e.g. Mid-market B2B SaaS RevOps leaders (200–2,000 employees) who own forecast "
            "accuracy but lack engineering support and fear another failed rollout."
        ),
        help="Who is the buyer? Their role, pains, and triggers.",
    )

    brief["goals"] = st.text_input(
        "Primary goal (optional)",
        value=brief.get("goals", ""),
        placeholder="e.g. Drive qualified free-trial signups in the first 30 days",
    )

    st.session_state.gtm_brief = brief

    user_input = build_user_input_from_config(brief)
    with st.expander("Query preview", expanded=False):
        st.code(user_input, language=None)

    errors = validate_gtm_brief(brief.get("product", ""), brief.get("audience", ""))
    if errors:
        for err in errors:
            st.caption(f"⚠ {err}")

    col1, col2 = st.columns([1, 3])
    with col1:
        can_run = not errors
        if st.button("Start Run", type="primary", disabled=not can_run):
            try:
                api.run_orca(brief, background=True)
                with st.spinner("ORCA pipeline running (Research → Strategy → Content → Brand)…"):
                    if poll_orca_until_complete(api):
                        st.success("Pipeline complete. Open **Dashboard** to view outputs.")
                    else:
                        st.warning("Pipeline did not finish successfully — check API logs.")
            except httpx.HTTPStatusError as exc:
                st.error(f"Run failed ({exc.response.status_code}): {exc.response.text}")
            except httpx.HTTPError as exc:
                st.error(f"API error: {exc}")

    with col2:
        st.caption("Required: Product and Audience. ORCA runs in the background via the API.")
