"""Analysis Agent dashboard — load, normalize, and render UI JSON."""

from __future__ import annotations

import html
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

from ui.utils.lucide_icons import lucide_heading, lucide_icon

from project_paths import OUTPUT_RUNS_DIR

ROOT_DIR = Path(__file__).resolve().parent.parent.parent

PAGE_TITLE = "Analysis"
PAGE_SUBTITLE = (
    "Track campaign Performance, Metric Computations, Financial Evaluation, "
    "Efficiency Assessment, and Structured Performance Summary."
)

METRIC_CARD_DEFS: list[tuple[str, str, str, str]] = [
    ("ctr_percent", "CTR", "%", "percent"),
    ("engagement_rate_percent", "Engagement Rate", "%", "message-square"),
    ("lead_conversion_rate_percent", "Lead Conversion Rate", "%", "target"),
    ("conversion_rate_percent", "Conversion Rate", "%", "circle-check"),
    ("roi_percent", "ROI", "%", "circle-dollar-sign"),
    ("leads", "Total Leads", "", "users"),
    ("conversions", "Total Conversions", "", "badge-check"),
    ("total_cost", "Total Cost", "$", "wallet"),
    ("total_revenue", "Total Revenue", "$", "bar-chart-3"),
]

FUNNEL_STEPS: list[tuple[str, str, str]] = [
    ("impressions", "Impressions", "funnel-step-impressions"),
    ("unique_users", "Unique Users", "funnel-step-users"),
    ("clicks", "Clicks", "funnel-step-clicks"),
    ("engagements", "Engagements", "funnel-step-engagements"),
    ("leads", "Leads", "funnel-step-leads"),
    ("conversions", "Conversions", "funnel-step-conversions"),
]

_SECTION_TYPE_PATTERNS: list[tuple[str, str]] = [
    (r"performance\s+summary", "performance_summary"),
    (r"ctr\s+analysis", "ctr_analysis"),
    (r"engagement\s+analysis", "engagement_analysis"),
    (r"lead\s+analysis", "lead_analysis"),
    (r"conversion\s+analysis", "conversion_analysis"),
    (r"roi\s+analysis", "roi_analysis"),
    (r"strengths", "strengths"),
    (r"weaknesses", "weaknesses"),
    (r"key\s+insights", "key_insights"),
]

_HIGHLIGHT_TYPES = frozenset({"strengths", "weaknesses", "key_insights"})

_NUMBER_RE = r"([\d,]+(?:\.\d+)?)"
_PERCENT_RE = r"([\d.]+)\s*%"


def load_analysis_ui(run_id: str) -> dict | None:
    """Load analysis.ui.json for a run."""
    path = OUTPUT_RUNS_DIR / run_id / "analysis.ui.json"
    if not path.is_file():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def get_field(data: Any, possible_keys: list[str], default: str = "Not specified") -> str:
    """Return the first non-empty value for any of the given keys."""
    if not isinstance(data, dict):
        return default
    for key in possible_keys:
        value = data.get(key)
        if value is None:
            continue
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return str(value)
        if isinstance(value, list) and value:
            return ", ".join(str(v) for v in value[:8])
    return default


def _parse_number(text: str) -> float | None:
    if not text:
        return None
    cleaned = text.replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def _coerce_metric_value(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str) and value.strip():
        return _parse_number(value)
    return None


def _first_match(pattern: str, text: str, flags: int = re.IGNORECASE) -> float | None:
    match = re.search(pattern, text or "", flags)
    if not match:
        return None
    return _parse_number(match.group(1))


def _section_by_type(sections: list[dict[str, Any]], section_type: str) -> dict[str, Any] | None:
    for section in sections:
        if isinstance(section, dict) and section.get("type") == section_type:
            return section
    return None


def _section_body_by_type(sections: list[dict[str, Any]], section_type: str) -> str:
    section = _section_by_type(sections, section_type)
    return (section.get("body") or "") if section else ""


def _derive_section_type(title: str) -> str:
    normalized = re.sub(r"^\d+\.\s*", "", title or "").strip().lower()
    for pattern, slug in _SECTION_TYPE_PATTERNS:
        if re.search(pattern, normalized):
            return slug
    slug = re.sub(r"[^a-z0-9]+", "_", normalized).strip("_")
    return slug or "section"


def extract_list_items(section_body: str) -> list[str]:
    """Parse bullet list items from section body text."""
    if not section_body or not str(section_body).strip():
        return []
    items: list[str] = []
    for line in str(section_body).splitlines():
        stripped = line.strip()
        match = re.match(r"^[-*•]\s+(.+)$", stripped)
        if match:
            item = match.group(1).strip()
            if item:
                items.append(item)
    if items:
        return items
    for chunk in re.split(r"\n\s*[-*•]\s+", str(section_body)):
        chunk = chunk.strip()
        if chunk and not chunk.startswith("#"):
            items.append(chunk)
    return items


def _parse_performance_summary(body: str) -> dict[str, float | None]:
    return {
        "impressions": _first_match(rf"{_NUMBER_RE}\s+impressions", body),
        "unique_users": _first_match(rf"{_NUMBER_RE}\s+unique users", body),
        "clicks": _first_match(rf"{_NUMBER_RE}\s+clicks", body),
        "engagements": _first_match(
            rf"(?:engagement of|total engagement of|total of)\s+{_NUMBER_RE}", body
        ) or _first_match(rf"{_NUMBER_RE}\s+(?:total\s+)?engagements?", body),
        "leads": _first_match(rf"acquired\s+{_NUMBER_RE}\s+leads", body)
        or _first_match(rf"{_NUMBER_RE}\s+leads", body),
        "conversions": _first_match(rf"converted\s+{_NUMBER_RE}", body)
        or _first_match(rf"{_NUMBER_RE}\s+conversions?", body),
        "total_cost": _first_match(r"(?:total cost of|cost of)\s*\$?([\d,]+(?:\.\d+)?)", body)
        or _first_match(r"\$([\d,]+(?:\.\d+)?)[^.\n]*\bcost\b", body),
        "total_revenue": _first_match(r"revenue of\s*\$?([\d,]+(?:\.\d+)?)", body)
        or _first_match(r"\$([\d,]+(?:\.\d+)?)[^.\n]*\brevenue\b", body),
    }


def _parse_section_metrics(sections: list[dict[str, Any]]) -> dict[str, float | None]:
    parsed: dict[str, float | None] = {}
    perf_body = _section_body_by_type(sections, "performance_summary")
    if perf_body:
        parsed.update(_parse_performance_summary(perf_body))

    ctr_body = _section_body_by_type(sections, "ctr_analysis")
    if ctr_body:
        parsed["ctr_percent"] = _first_match(
            rf"(?:CTR|Click-Through Rate).*(?:is|of)\s+{_PERCENT_RE}", ctr_body
        ) or _first_match(rf"CTR.*?{_PERCENT_RE}", ctr_body)

    engagement_body = _section_body_by_type(sections, "engagement_analysis")
    if engagement_body:
        parsed["engagement_rate_percent"] = _first_match(
            rf"engagement rate.*?(?:is|of)\s+{_PERCENT_RE}", engagement_body
        )

    lead_body = _section_body_by_type(sections, "lead_analysis")
    if lead_body:
        if parsed.get("leads") is None:
            parsed["leads"] = _first_match(rf"generated\s+{_NUMBER_RE}\s+leads", lead_body)
        parsed["lead_conversion_rate_percent"] = _first_match(
            rf"lead conversion rate of\s+{_PERCENT_RE}", lead_body
        )

    conversion_body = _section_body_by_type(sections, "conversion_analysis")
    if conversion_body:
        parsed["conversion_rate_percent"] = _first_match(
            rf"conversion rate.*?(?:is|of|stands at)\s+{_PERCENT_RE}", conversion_body
        )
        if parsed.get("conversions") is None:
            parsed["conversions"] = _first_match(
                rf"{_NUMBER_RE}\s+conversions?", conversion_body
            )

    roi_body = _section_body_by_type(sections, "roi_analysis")
    if roi_body:
        parsed["roi_percent"] = _first_match(
            rf"(?:ROI|return on investment).*(?:of|is)\s+{_PERCENT_RE}", roi_body
        )
        if parsed.get("total_revenue") is None:
            parsed["total_revenue"] = _first_match(
                r"revenue of\s*\$?([\d,]+(?:\.\d+)?)", roi_body
            )
        if parsed.get("total_cost") is None:
            parsed["total_cost"] = _first_match(
                r"(?:total )?cost of\s*\$?([\d,]+(?:\.\d+)?)", roi_body
            )

    return parsed


def normalize_run_metadata(analysis_ui: dict[str, Any]) -> dict[str, str]:
    """Normalize run metadata for the header strip."""
    if not isinstance(analysis_ui, dict):
        return {
            "run_id": "Not specified",
            "generated_at": "Not specified",
            "status": "Not specified",
            "source_datasets": "Not specified",
        }

    generated = analysis_ui.get("generated_at") or analysis_ui.get("updated_at") or ""
    generated_display = "Not specified"
    if generated:
        try:
            dt = datetime.fromisoformat(str(generated).replace("Z", "+00:00"))
            generated_display = dt.strftime("%b %d, %Y · %I:%M %p")
        except ValueError:
            generated_display = str(generated)

    input_summary = analysis_ui.get("input_summary")
    source_datasets = "Not specified"
    if isinstance(input_summary, dict):
        parts = [f"{k}: {v}" for k, v in input_summary.items() if v]
        source_datasets = ", ".join(parts) if parts else "Not specified"
    elif isinstance(input_summary, str) and input_summary.strip():
        try:
            parsed = json.loads(input_summary)
            if isinstance(parsed, dict):
                parts = [f"{k}: {v}" for k, v in parsed.items() if v]
                source_datasets = ", ".join(parts) if parts else input_summary.strip()
            else:
                source_datasets = input_summary.strip()
        except json.JSONDecodeError:
            source_datasets = input_summary.strip()

    return {
        "run_id": get_field(analysis_ui, ["run_id"], default="Not specified"),
        "generated_at": generated_display,
        "status": get_field(analysis_ui, ["status"], default="Not specified"),
        "source_datasets": source_datasets,
    }


def normalize_metrics(analysis_ui: dict[str, Any]) -> dict[str, float | None]:
    """Normalize metric values from top-level metrics and section bodies."""
    if not isinstance(analysis_ui, dict):
        return {}

    sections = normalize_sections(analysis_ui)
    section_parsed = _parse_section_metrics(sections)

    raw_metrics = analysis_ui.get("metrics")
    if not isinstance(raw_metrics, dict):
        raw_metrics = {}

    keys = [
        "ctr_percent",
        "engagement_rate_percent",
        "lead_conversion_rate_percent",
        "conversion_rate_percent",
        "roi_percent",
        "impressions",
        "unique_users",
        "clicks",
        "engagements",
        "leads",
        "conversions",
        "total_cost",
        "total_revenue",
    ]

    normalized: dict[str, float | None] = {}
    for key in keys:
        top_value = _coerce_metric_value(raw_metrics.get(key))
        section_value = section_parsed.get(key)
        normalized[key] = top_value if top_value is not None else section_value
    return normalized


def normalize_sections(analysis_ui: dict[str, Any]) -> list[dict[str, str]]:
    """Normalize report sections with title, body, and type slug."""
    raw_sections = analysis_ui.get("sections") if isinstance(analysis_ui, dict) else None
    if not isinstance(raw_sections, list):
        return []

    normalized: list[dict[str, str]] = []
    for item in raw_sections:
        if isinstance(item, str):
            normalized.append({
                "title": "Section",
                "body": item,
                "type": "section",
            })
            continue
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "Section").strip()
        body = str(item.get("body") or "").strip()
        if not title and not body:
            continue
        normalized.append({
            "title": title or "Section",
            "body": body,
            "type": _derive_section_type(title),
        })
    return normalized


def _format_metric_display(key: str, value: float | None, suffix: str) -> str:
    if value is None:
        return "Not specified"
    if suffix == "%":
        text = f"{value:g}%"
    elif suffix == "$":
        if value >= 1000:
            text = f"${value:,.0f}"
        elif value == int(value):
            text = f"${int(value):,}"
        else:
            text = f"${value:,.2f}"
    else:
        text = f"{int(value):,}" if value == int(value) else f"{value:,.2f}"
    return text


def _metric_card_class(key: str) -> str:
    if key in {"ctr_percent", "engagement_rate_percent", "lead_conversion_rate_percent", "conversion_rate_percent"}:
        return "analysis-metric-funnel"
    if key in {"roi_percent", "total_cost", "total_revenue"}:
        return "analysis-metric-financial"
    return "analysis-metric-volume"


def render_run_metadata_header(metadata: dict[str, str]) -> None:
    """Render the run info strip at the top of the page."""
    items = [
        ("Run ID", metadata.get("run_id", "Not specified")),
        ("Generated at", metadata.get("generated_at", "Not specified")),
        ("Status", metadata.get("status", "Not specified")),
        ("Source datasets", metadata.get("source_datasets", "Not specified")),
    ]
    cells = "".join(
        f'<div class="analysis-meta-cell">'
        f'<span class="analysis-meta-label">{html.escape(label)}</span>'
        f'<span class="analysis-meta-value">{html.escape(value)}</span>'
        f"</div>"
        for label, value in items
    )
    st.markdown(
        f'<div class="analysis-meta-strip">{cells}</div>',
        unsafe_allow_html=True,
    )


def _render_funnel_chart(metrics: dict[str, float | None]) -> None:
    steps: list[tuple[str, str, float]] = []
    for key, label, css_class in FUNNEL_STEPS:
        value = metrics.get(key)
        if value is not None:
            steps.append((label, css_class, value))

    if len(steps) < 2:
        return

    max_value = max(v for _, _, v in steps)
    bars = []
    for label, css_class, value in steps:
        width_pct = max(12, round((value / max_value) * 100)) if max_value else 12
        display = f"{int(value):,}" if value == int(value) else f"{value:,.1f}"
        bars.append(
            f'<div class="analysis-funnel-row">'
            f'<div class="analysis-funnel-label">{html.escape(label)}</div>'
            f'<div class="analysis-funnel-track">'
            f'<div class="analysis-funnel-bar {css_class}" style="width:{width_pct}%;">'
            f'<span class="analysis-funnel-value">{html.escape(display)}</span>'
            f"</div></div></div>"
        )

    st.markdown(
        '<div class="analysis-chart-card">'
        f'<div class="analysis-chart-title">{lucide_heading("filter", "Campaign Funnel")}</div>'
        f'<div class="analysis-funnel-chart">{"".join(bars)}</div>'
        "</div>",
        unsafe_allow_html=True,
    )


def _render_financial_chart(metrics: dict[str, float | None]) -> None:
    cost = metrics.get("total_cost")
    revenue = metrics.get("total_revenue")
    roi = metrics.get("roi_percent")

    if cost is None and revenue is None and roi is None:
        return

    bars_html = []
    chart_max = max(v for v in (cost, revenue) if v is not None) or 1

    if cost is not None:
        width = max(8, round((cost / chart_max) * 100))
        display = _format_metric_display("total_cost", cost, "$")
        bars_html.append(
            f'<div class="analysis-fin-row">'
            f'<span class="analysis-fin-label">Cost</span>'
            f'<div class="analysis-fin-track"><div class="analysis-fin-bar cost" style="width:{width}%;">'
            f"{html.escape(display)}</div></div></div>"
        )
    if revenue is not None:
        width = max(8, round((revenue / chart_max) * 100))
        display = _format_metric_display("total_revenue", revenue, "$")
        bars_html.append(
            f'<div class="analysis-fin-row">'
            f'<span class="analysis-fin-label">Revenue</span>'
            f'<div class="analysis-fin-track"><div class="analysis-fin-bar revenue" style="width:{width}%;">'
            f"{html.escape(display)}</div></div></div>"
        )

    roi_html = ""
    if roi is not None:
        roi_width = min(100, max(8, round(roi / 3)))
        roi_html = (
            f'<div class="analysis-roi-gauge">'
            f'<div class="analysis-roi-label">ROI</div>'
            f'<div class="analysis-roi-track"><div class="analysis-roi-fill" style="width:{roi_width}%;"></div></div>'
            f'<div class="analysis-roi-value">{html.escape(_format_metric_display("roi_percent", roi, "%"))}</div>'
            f"</div>"
        )

    st.markdown(
        '<div class="analysis-chart-card">'
        f'<div class="analysis-chart-title">{lucide_heading("chart-column", "Financial Overview")}</div>'
        f'{"".join(bars_html)}{roi_html}'
        "</div>",
        unsafe_allow_html=True,
    )


def render_metric_cards(metrics: dict[str, float | None]) -> None:
    """Render styled metric summary cards."""
    has_any = any(metrics.get(key) is not None for key, *_ in METRIC_CARD_DEFS)
    if not has_any:
        st.info("Metrics not available — see Performance Report for details.")
        return

    cards: list[str] = []
    for key, label, suffix, icon_name in METRIC_CARD_DEFS:
        value = metrics.get(key)
        display = _format_metric_display(key, value, suffix)
        css_class = _metric_card_class(key)
        icon_html = lucide_icon(icon_name, size=20, css_class="lucide-icon analysis-metric-icon-svg")
        cards.append(
            f'<div class="analysis-metric-card {css_class}">'
            f'<div class="analysis-metric-icon">{icon_html}</div>'
            f'<div class="analysis-metric-body">'
            f'<div class="analysis-metric-value">{html.escape(display)}</div>'
            f'<div class="analysis-metric-label">{html.escape(label)}</div>'
            f"</div></div>"
        )

    st.markdown(
        f'<div class="analysis-metrics-grid">{"".join(cards)}</div>',
        unsafe_allow_html=True,
    )


def render_strengths_weaknesses(sections: list[dict[str, str]]) -> None:
    """Render strengths and weaknesses in a two-column highlight block."""
    strengths_section = _section_by_type(sections, "strengths")
    weaknesses_section = _section_by_type(sections, "weaknesses")
    if not strengths_section and not weaknesses_section:
        return

    def _column_html(
        section: dict[str, str] | None,
        css_class: str,
        heading: str,
        icon_name: str,
    ) -> str:
        heading_html = lucide_heading(icon_name, heading, size=18)
        if not section:
            return (
                f'<div class="analysis-sw-column {css_class}">'
                f'<div class="analysis-sw-heading">{heading_html}</div>'
                f'<p class="analysis-sw-empty">Not specified</p></div>'
            )
        items = extract_list_items(section.get("body", ""))
        if items:
            lis = "".join(f"<li>{html.escape(item)}</li>" for item in items)
            body_html = f"<ul class='analysis-sw-list'>{lis}</ul>"
        else:
            body_html = f"<p class='analysis-sw-fallback'>{html.escape(section.get('body', ''))}</p>"
        return (
            f'<div class="analysis-sw-column {css_class}">'
            f'<div class="analysis-sw-heading">{heading_html}</div>'
            f"{body_html}</div>"
        )

    st.markdown(
        '<div class="analysis-sw-grid">'
        f"{_column_html(strengths_section, 'analysis-sw-strengths', 'Strengths', 'thumbs-up')}"
        f"{_column_html(weaknesses_section, 'analysis-sw-weaknesses', 'Weaknesses', 'alert-triangle')}"
        "</div>",
        unsafe_allow_html=True,
    )


def _section_icon_name(section_type: str) -> str:
    icons = {
        "performance_summary": "clipboard-list",
        "ctr_analysis": "mouse-pointer-click",
        "engagement_analysis": "message-square",
        "lead_analysis": "target",
        "conversion_analysis": "circle-check",
        "roi_analysis": "circle-dollar-sign",
        "strengths": "thumbs-up",
        "weaknesses": "alert-triangle",
        "key_insights": "lightbulb",
    }
    return icons.get(section_type, "file-text")


def _section_card_class(section_type: str) -> str:
    if section_type == "strengths":
        return "analysis-section-strengths"
    if section_type == "weaknesses":
        return "analysis-section-weaknesses"
    if section_type == "key_insights":
        return "analysis-section-insights"
    return "analysis-section-default"


def _render_section_card(section: dict[str, str]) -> None:
    section_type = section.get("type", "section")
    title = section.get("title", "Section")
    body = section.get("body", "")
    icon_name = _section_icon_name(section_type)
    header_html = lucide_heading(icon_name, title, size=17)
    css_class = _section_card_class(section_type)

    if section_type in _HIGHLIGHT_TYPES:
        items = extract_list_items(body)
        if items:
            lis = "".join(f"<li>{html.escape(item)}</li>" for item in items)
            body_html = f"<ul class='analysis-section-list'>{lis}</ul>"
        else:
            body_html = f"<p class='analysis-section-body'>{html.escape(body)}</p>"
    else:
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
        if not paragraphs:
            paragraphs = [body] if body else []
        body_html = "".join(
            f"<p class='analysis-section-body'>{html.escape(p)}</p>" for p in paragraphs
        )

    st.markdown(
        f'<div class="analysis-report-card {css_class}">'
        f'<div class="analysis-report-header">{header_html}</div>'
        f"{body_html}</div>",
        unsafe_allow_html=True,
    )


def render_performance_report(
    sections: list[dict[str, str]],
    *,
    keyword: str = "",
    insights_only: bool = False,
) -> None:
    """Render performance report section cards."""
    if not sections:
        st.warning("No performance sections were found.")
        return

    filtered = sections
    if keyword:
        needle = keyword.lower()
        filtered = [
            s for s in filtered
            if needle in (s.get("title") or "").lower()
            or needle in (s.get("body") or "").lower()
        ]

    if insights_only:
        filtered = [s for s in filtered if s.get("type") in _HIGHLIGHT_TYPES]

    if not filtered:
        st.info("No sections match the current filters.")
        return

    for section in filtered:
        _render_section_card(section)


def render_analysis_page(analysis_ui: dict[str, Any]) -> None:
    """Render the full Analysis page from UI JSON."""
    if not isinstance(analysis_ui, dict):
        st.error("Analysis data was not found in structured format.")
        return

    status = analysis_ui.get("status", "completed")
    badge = "● Analysis Complete" if status == "completed" else f"● Analysis {str(status).title()}"

    st.markdown(
        f'<div class="hero-card analysis-hero">'
        f'<div class="hero-top">'
        f'<div><h2 class="hero-title">{html.escape(PAGE_TITLE)}</h2>'
        f'<p class="hero-subtitle">{html.escape(PAGE_SUBTITLE)}</p></div>'
        f'<div class="hero-badge">{html.escape(badge)}</div>'
        f"</div></div>",
        unsafe_allow_html=True,
    )

    metadata = normalize_run_metadata(analysis_ui)
    render_run_metadata_header(metadata)

    sections = normalize_sections(analysis_ui)
    metrics = normalize_metrics(analysis_ui)

    st.markdown('<div class="analysis-panel">', unsafe_allow_html=True)

    if not sections and not any(v is not None for v in metrics.values()):
        st.error("Analysis data was not found in structured format.")
    else:
        render_metric_cards(metrics)

        chart_left, chart_right = st.columns(2, gap="large")
        with chart_left:
            _render_funnel_chart(metrics)
        with chart_right:
            _render_financial_chart(metrics)

        render_strengths_weaknesses(sections)

        st.markdown(
            '<div class="analysis-report-shell">'
            '<div class="section-card-header">Performance Report</div>'
            '<p class="content-gallery-caption">Campaign performance analysis by section.</p>'
            "</div>",
            unsafe_allow_html=True,
        )

        filter_col1, filter_col2 = st.columns([2, 1], gap="medium")
        with filter_col1:
            keyword = st.text_input(
                "Filter sections",
                value="",
                placeholder="Search by keyword or title…",
                key="analysis_section_filter",
            )
        with filter_col2:
            insights_only = st.checkbox(
                "Insights only",
                value=False,
                help="Show only Strengths, Weaknesses, and Key Insights",
                key="analysis_insights_only",
            )

        render_performance_report(sections, keyword=keyword.strip(), insights_only=insights_only)

    st.markdown("</div>", unsafe_allow_html=True)

    with st.expander("Raw Analysis JSON"):
        st.json(analysis_ui)
