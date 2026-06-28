"""Branded header with live agent status."""

import html

import streamlit as st

from ui.api_client import StratovaAPI
from ui.config import load_logo_svg


def _status_label(jobs: dict) -> str:
    if jobs.get("orca") == "running":
        return "● ORCA running"
    running = [name for name, state in jobs.items() if state == "running"]
    if running:
        return f"● {running[0].title()} running"
    errors = [name for name, state in jobs.items() if str(state).startswith("error")]
    if errors:
        return f"● {errors[0].title()} error"
    return "● All agents active"


def render_header(api: StratovaAPI) -> None:
    try:
        health = api.health()
        jobs = health.get("jobs", {})
        status = _status_label(jobs)
    except Exception:
        status = "● API offline"

    logo = load_logo_svg()
    st.markdown(
        f"""
        <div class="header">
            <div class="logo-section">
                <div class="header-logo">{logo}</div>
                <div>
                    <h1>Stratova, GTM Agentic AI</h1>
                    <p>Marketing Intelligence System</p>
                </div>
            </div>
            <div class="status">{html.escape(status)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
