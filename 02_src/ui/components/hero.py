"""Hero summary card with derived metrics."""

import html

import streamlit as st


def render_hero(
    title: str,
    subtitle: str,
    status_badge: str,
    metrics: dict[str, str],
    metric_labels: dict[str, str] | None = None,
) -> None:
    labels = metric_labels or {
        "sources": "SOURCES",
        "data_points": "DATA POINTS",
        "confidence": "CONFIDENCE",
        "processing_time": "TIME",
    }
    metric_cells = "".join(
        f'<div class="metric-cell">'
        f'<div class="metric-value">{html.escape(metrics.get(key, "—"))}</div>'
        f'<div class="metric-label">{html.escape(label)}</div>'
        f"</div>"
        for key, label in labels.items()
    )

    st.markdown(
        f"""
        <div class="hero-card">
            <div class="hero-top">
                <div>
                    <h2 class="hero-title">{html.escape(title)}</h2>
                    <p class="hero-subtitle">{html.escape(subtitle)}</p>
                </div>
                <div class="hero-badge">{html.escape(status_badge)}</div>
            </div>
            <div class="metric-row">{metric_cells}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
