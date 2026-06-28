"""Load orchestration run outputs for Streamlit (latest run only)."""

from __future__ import annotations

import json
import os
from pathlib import Path

from project_paths import OUTPUT_RUNS_DIR

LATEST_RUN_PATH = OUTPUT_RUNS_DIR.parent / "latest_run.json"

# UI tab id -> orchestrator agent key in ui_index.json
TAB_TO_AGENT: dict[str, str] = {
    "research": "research",
    "strategy": "strategy",
    "content": "content",
    "brand": "brand_alignment",
    "analysis": "analysis",
}

# Orchestrator agent key -> UI reports dict key
AGENT_TO_REPORT: dict[str, str] = {
    "research": "research",
    "strategy": "strategy",
    "content": "content",
    "brand_alignment": "brand",
    "analysis": "analysis",
}


def _read_json(path: Path | str) -> dict | None:
    path = Path(path)
    if not path.is_file():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def load_latest_run() -> dict | None:
    """Read outputs/latest_run.json; return None if missing or invalid."""
    return _read_json(LATEST_RUN_PATH)


def load_ui_index() -> dict | None:
    """Load ui_index.json from the path recorded in latest_run.json."""
    latest = load_latest_run()
    if not latest:
        return None

    ui_index_path = latest.get("ui_index_path")
    if not ui_index_path:
        run_dir = latest.get("run_dir")
        if run_dir:
            ui_index_path = str(Path(run_dir) / "ui_index.json")

    if not ui_index_path:
        return None

    return _read_json(ui_index_path)


def get_agent_index_entry(tab_id: str) -> dict | None:
    """Return the ui_index entry for a UI tab (e.g. research -> agents.research)."""
    ui_index = load_ui_index()
    if not ui_index:
        return None

    agent_key = TAB_TO_AGENT.get(tab_id, tab_id)
    entry = ui_index.get("agents", {}).get(agent_key)
    return entry if isinstance(entry, dict) else None


def load_agent_ui(tab_id: str) -> dict | None:
    """Load the agent UI JSON file for a tab from the latest run."""
    entry = get_agent_index_entry(tab_id)
    if not entry:
        return None

    ui_file_path = entry.get("ui_file_path") or entry.get("full_file_path")
    if not ui_file_path:
        return None

    return _read_json(ui_file_path)


def reports_from_latest_run() -> dict[str, bool]:
    """
    Pipeline completion flags from the latest run's ui_index.

    Returns {research, strategy, content, brand} with True when status is completed.
    """
    reports = {key: False for key in ("research", "strategy", "content", "brand", "analysis")}
    ui_index = load_ui_index()
    if not ui_index:
        return reports

    for agent_key, entry in (ui_index.get("agents") or {}).items():
        if not isinstance(entry, dict):
            continue
        report_key = AGENT_TO_REPORT.get(agent_key)
        if report_key and entry.get("status") == "completed":
            reports[report_key] = True

    return reports
