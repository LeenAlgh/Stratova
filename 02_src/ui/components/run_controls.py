"""Agent run controls — ORCA job polling for New Run."""

import time

import streamlit as st

from ui.api_client import StratovaAPI


def poll_orca_until_complete(api: StratovaAPI, timeout_sec: int = 3600) -> bool:
    """Poll until the ORCA pipeline job completes or fails."""
    deadline = time.time() + timeout_sec
    progress = st.progress(0, text="ORCA pipeline running…")

    while time.time() < deadline:
        jobs = api.job_status()
        state = jobs.get("orca", "idle")
        if state == "complete":
            progress.progress(100, text="ORCA pipeline complete")
            return True
        if str(state).startswith("error"):
            progress.empty()
            st.error(f"ORCA pipeline failed: {state}")
            return False
        elapsed = timeout_sec - (deadline - time.time())
        pct = min(int(elapsed / timeout_sec * 90), 90)
        progress.progress(pct, text="ORCA pipeline running…")
        time.sleep(3)

    progress.empty()
    st.warning("ORCA pipeline timed out — check API logs.")
    return False
