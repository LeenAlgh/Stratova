"""Styled section rendering for Strategy Agent UI JSON."""

from __future__ import annotations

import html
import re
from typing import Any

import streamlit as st

from ui.utils.section_fields import parse_bullet_fields, parse_flat_bullet_fields

_BULLET_LINE_RE = re.compile(r"^[-*]\s+\*\*(.+?)\*\*\s*:?\s*(.*)$")

_ICP_TITLES = frozenset({
    "firmographics",
    "geography",
    "technology maturity",
    "pain points",
    "buying triggers",
    "decision criteria",
    "disqualifiers",
})

_PILLAR_FIELDS = (
    ("Core Message", ("core message",)),
    ("Persona Match", ("persona match",)),
    ("Research Support", ("research support",)),
    ("Brand Alignment", ("brand alignment note", "brand alignment")),
)


def _parse_bullet_fields(body: str) -> dict[str, str]:
    return parse_bullet_fields(body)


def _field_value(fields: dict[str, str], *keys: str, default: str = "Not specified") -> str:
    for key in keys:
        value = fields.get(key.lower())
        if value and value.strip():
            return value.strip()
    return default


def _title_suffix(title: str) -> str:
    if ":" in title:
        return title.split(":", 1)[1].strip()
    return re.sub(r"^\d+\.\s*", "", title).strip()


def _clean_title(title: str) -> str:
    return re.sub(r"^\d+\.\s*", "", title or "Section").strip()


def _is_persona(title: str) -> bool:
    return bool(re.search(r"persona\s*\d", title, re.IGNORECASE))


def _is_pillar(title: str) -> bool:
    return bool(re.search(r"pillar\s*\d", title, re.IGNORECASE))


def _is_month(title: str) -> bool:
    return bool(re.match(r"month\s*\d+", title, re.IGNORECASE))


def _is_handoff(title: str) -> bool:
    lowered = title.lower()
    return "handoff to content" in lowered or "handoff to content agent" in lowered


def _is_icp_component(title: str) -> bool:
    return _clean_title(title).lower() in _ICP_TITLES


def _is_combined_icp_section(title: str) -> bool:
    lowered = _clean_title(title).lower()
    return "ideal customer profile" in lowered or lowered in {"icp", "ideal customer profile (icp)"}


def _is_channel_section(title: str) -> bool:
    lowered = _clean_title(title).lower()
    return "recommended channels" in lowered or "channel strategy" in lowered


def _icp_blocks_from_sections(sections: list[dict[str, Any]]) -> list[dict[str, str]]:
    blocks: list[dict[str, str]] = []
    for section in sections:
        title = section.get("title") or ""
        body = section.get("body") or ""
        if _is_combined_icp_section(title):
            for key, value in parse_bullet_fields(body).items():
                label = " ".join(word.capitalize() for word in key.split())
                blocks.append({"title": label, "body": value})
        elif _is_icp_component(title):
            blocks.append({"title": _clean_title(title), "body": body})
    return blocks


def _parse_channel_table(body: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    table_lines = [line.strip() for line in (body or "").splitlines() if line.strip().startswith("|")]
    if len(table_lines) < 3:
        return rows

    for line in table_lines[2:]:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        priority = _priority_label(cells[0])
        badge_class = "priority-high" if priority.lower() == "high" else "priority-medium"
        if priority.lower() == "low":
            badge_class = "priority-low"
        rows.append(
            {
                "name": cells[1] if len(cells) > 1 else "Channel",
                "priority": priority,
                "badge_class": badge_class,
                "rationale": cells[2] if len(cells) > 2 else "Not specified",
                "target_persona": cells[3] if len(cells) > 3 else "Not specified",
                "content_types": cells[4] if len(cells) > 4 else "Not specified",
                "frequency": cells[5] if len(cells) > 5 else "Not specified",
                "kpi": cells[6] if len(cells) > 6 else "Not specified",
                "brand_fit": "Not specified",
            }
        )
    return rows


def _find_channel_section(sections: list[dict[str, Any]]) -> dict[str, Any] | None:
    for section in sections:
        if _is_channel_section(section.get("title") or ""):
            return section
    return None


def _parse_channels(body: str) -> list[dict[str, str]]:
    channels = _parse_numbered_channels(body)
    if channels:
        return channels
    return _parse_channel_table(body)


def _render_labeled_field(label: str, value: str) -> str:
    display = value if value and value.strip() else "Not specified"
    return (
        f'<div class="persona-field">'
        f'<div class="persona-field-label">{html.escape(label)}</div>'
        f'<div class="persona-field-value">{html.escape(display)}</div>'
        f"</div>"
    )


def _semicolon_items_to_html(text: str) -> str:
    """Render semicolon-separated items as labeled or plain field rows."""
    parts = [part.strip() for part in text.split(";") if part.strip()]
    if not parts:
        return ""
    chunks: list[str] = []
    for part in parts:
        if re.match(r"^[^:]+:\s*.+", part) and part.index(":") < 40:
            label, _, value = part.partition(":")
            chunks.append(_render_labeled_field(label.strip(), value.strip()))
        else:
            chunks.append(
                f'<div class="persona-field">'
                f'<div class="persona-field-value">{html.escape(part)}</div>'
                f"</div>"
            )
    return "".join(chunks)


def _bullets_to_card_html(body: str) -> str:
    """Convert markdown bullet content to inline HTML for a single st.markdown call."""
    fields = parse_bullet_fields(body)
    if not fields:
        fields = parse_flat_bullet_fields(body)
    if fields:
        return "".join(
            _render_labeled_field(label.replace("_", " ").title(), value)
            for label, value in fields.items()
            if value
        )

    if ";" in body:
        semicolon_html = _semicolon_items_to_html(body)
        if semicolon_html:
            return semicolon_html

    chunks: list[str] = []
    for line in (body or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        plain = re.sub(r"^[-*]\s+", "", stripped)
        if plain:
            chunks.append(
                f'<div class="persona-field">'
                f'<div class="persona-field-value">{html.escape(plain)}</div>'
                f"</div>"
            )
    if chunks:
        return "".join(chunks)
    text = (body or "").strip()
    if not text:
        return ""
    return f'<div class="strategy-card-body">{html.escape(text)}</div>'


def _build_strategy_card_html(
    heading: str,
    subheading: str = "",
    fields: list[tuple[str, str]] | None = None,
    body: str = "",
    badge: str = "",
    badge_class: str = "priority-medium",
) -> str:
    """Build card markup as one line so Streamlit does not escape nested divs."""
    pieces: list[str] = [
        '<div class="persona-card strategy-card">',
        '<div class="persona-card-header"><div>',
        f'<div class="persona-name">{html.escape(heading)}</div>',
    ]
    if subheading:
        pieces.append(f'<div class="persona-role">{html.escape(subheading)}</div>')
    pieces.append("</div>")
    if badge:
        pieces.append(
            f'<div class="persona-badges">'
            f'<span class="priority-badge {badge_class}">{html.escape(badge)}</span>'
            f"</div>"
        )
    pieces.append("</div>")

    if fields:
        for label, value in fields:
            pieces.append(_render_labeled_field(label, value))
    elif body:
        pieces.append(_bullets_to_card_html(body))

    pieces.append("</div>")
    return "".join(pieces)


def _render_strategy_card(
    heading: str,
    subheading: str = "",
    fields: list[tuple[str, str]] | None = None,
    body: str = "",
    badge: str = "",
    badge_class: str = "priority-medium",
) -> None:
    st.markdown(
        _build_strategy_card_html(
            heading,
            subheading=subheading,
            fields=fields,
            body=body,
            badge=badge,
            badge_class=badge_class,
        ),
        unsafe_allow_html=True,
    )


def _channel_name_from_match(raw_name: str, detail: str) -> str:
    name = raw_name.strip().rstrip(":")
    if name.lower() != "channel":
        return name

    for line in detail.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if not stripped.startswith(("-", "*")):
            inline = re.sub(r"^:\s*", "", stripped)
            if inline:
                return inline
        match = _BULLET_LINE_RE.match(stripped)
        if match and match.group(1).strip().rstrip(":").lower() == "channel":
            value = match.group(2).strip()
            if value:
                return value
    return "Channel"


def _priority_label(priority: str) -> str:
    if priority in {"1", "2"}:
        return "High"
    if priority in {"3", "4"}:
        return "Medium"
    if priority in {"5", "6", "7"}:
        return "Low"
    return priority or "Not specified"


def _channel_card_fields(channel: dict[str, str]) -> list[tuple[str, str]]:
    rows = [
        ("Rationale", channel.get("rationale", "Not specified")),
        ("Target Persona", channel.get("target_persona", "Not specified")),
        ("Content Types", channel.get("content_types", "Not specified")),
        ("Frequency", channel.get("frequency", "Not specified")),
        ("KPI", channel.get("kpi", "Not specified")),
    ]
    brand_fit = channel.get("brand_fit", "")
    if brand_fit and brand_fit != "Not specified":
        rows.append(("Brand Fit", brand_fit))
    return rows


def _parse_numbered_channels(body: str) -> list[dict[str, str]]:
    channels: list[dict[str, str]] = []
    if not body:
        return channels

    pattern = re.compile(
        r"^\s*(\d+)\.\s+\*\*(.+?)\*\*\s*(.*?)(?=^\s*\d+\.\s+\*\*|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    for match in pattern.finditer(body):
        raw_name = match.group(2).strip()
        detail = match.group(3).strip()
        fields = parse_flat_bullet_fields(detail)
        name = _channel_name_from_match(raw_name, detail)
        priority = _priority_label(_field_value(fields, "priority"))
        badge_class = "priority-high" if priority.lower() == "high" else "priority-medium"
        if priority.lower() == "low":
            badge_class = "priority-low"
        channels.append(
            {
                "name": name,
                "priority": priority,
                "badge_class": badge_class,
                "rationale": _field_value(fields, "rationale", "why this channel fits"),
                "target_persona": _field_value(fields, "target persona"),
                "content_types": _field_value(fields, "content types"),
                "frequency": _field_value(fields, "frequency"),
                "kpi": _field_value(fields, "kpi", "kpi to track"),
                "brand_fit": _field_value(fields, "brand fit"),
            }
        )
    return channels


def _month_sort_key(title: str) -> int:
    match = re.search(r"month\s*(\d+)", title, re.IGNORECASE)
    return int(match.group(1)) if match else 0


def _pillar_sort_key(title: str) -> int:
    match = re.search(r"pillar\s*(\d+)", title, re.IGNORECASE)
    return int(match.group(1)) if match else 0


def _render_column_cards(items: list[Any], render_fn) -> None:
    if not items:
        return

    st.markdown('<div class="strategy-grid-top-spacer"></div>', unsafe_allow_html=True)
    chunk_size = 3
    for row_index, row_start in enumerate(range(0, len(items), chunk_size)):
        if row_index > 0:
            st.markdown('<div class="strategy-grid-row-spacer"></div>', unsafe_allow_html=True)
        row_items = items[row_start : row_start + chunk_size]
        columns = st.columns(len(row_items), gap="large")
        for column, item in zip(columns, row_items):
            with column:
                render_fn(item)
    st.markdown('<div class="strategy-grid-bottom-spacer"></div>', unsafe_allow_html=True)


def render_pillars_section(sections: list[dict[str, Any]]) -> None:
    pillars = sorted(
        [s for s in sections if _is_pillar(s.get("title") or "")],
        key=lambda s: _pillar_sort_key(s.get("title") or ""),
    )
    if not pillars:
        return

    st.subheader("Messaging Pillars")
    st.caption("Core messages that shape positioning, content, and channel execution.")

    def _render_pillar(section: dict[str, Any]) -> None:
        title = section.get("title") or "Pillar"
        fields_map = _parse_bullet_fields(section.get("body") or "")
        card_fields = [
            (label, _field_value(fields_map, *keys))
            for label, keys in _PILLAR_FIELDS
        ]
        pillar_match = re.search(r"pillar\s*(\d+)", title, re.IGNORECASE)
        subheading = f"Pillar {pillar_match.group(1)}" if pillar_match else ""
        _render_strategy_card(_title_suffix(title), subheading=subheading, fields=card_fields)

    _render_column_cards(pillars, _render_pillar)


def render_timeline_section(sections: list[dict[str, Any]]) -> None:
    months = sorted(
        [s for s in sections if _is_month(s.get("title") or "")],
        key=lambda s: _month_sort_key(s.get("title") or ""),
    )
    if not months:
        return

    st.subheader("Go-To-Market Timeline")
    st.caption("Phased execution plan for the first months of the strategy.")

    def _render_month(section: dict[str, Any]) -> None:
        title = section.get("title") or "Month"
        body = section.get("body") or ""
        phase = _title_suffix(title)
        month_label = re.search(r"month\s*\d+", title, re.IGNORECASE)
        heading = month_label.group(0).title() if month_label else _clean_title(title)
        _render_strategy_card(heading, subheading=phase, body=body)

    _render_column_cards(months, _render_month)


def render_channels_section(sections: list[dict[str, Any]]) -> None:
    channel_section = _find_channel_section(sections)
    if not channel_section:
        return

    channels = _parse_channels(channel_section.get("body") or "")
    if not channels:
        return

    st.subheader("Recommended Channels")
    st.caption("Priority channels, cadence, and KPIs for reaching target personas.")

    def _render_channel(channel: dict[str, str]) -> None:
        _render_strategy_card(
            channel["name"],
            badge=f"Priority: {channel['priority']}",
            badge_class=channel["badge_class"],
            fields=_channel_card_fields(channel),
        )

    _render_column_cards(channels, _render_channel)


def render_icp_section(sections: list[dict[str, Any]]) -> None:
    icp_sections = _icp_blocks_from_sections(sections)
    if not icp_sections:
        return

    st.subheader("Ideal Customer Profile")
    st.caption("Firmographic fit, pain points, triggers, and disqualifiers for target accounts.")

    def _render_icp_block(section: dict[str, Any]) -> None:
        title = _clean_title(section.get("title") or "ICP")
        body = section.get("body") or ""
        _render_strategy_card(title, body=body)

    _render_column_cards(icp_sections, _render_icp_block)


def _classify_sections(sections: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    buckets: dict[str, list[dict[str, Any]]] = {
        "early": [],
        "icp": [],
        "positioning": [],
        "pillars": [],
        "channels": [],
        "months": [],
        "late": [],
    }
    for section in sections:
        if not isinstance(section, dict):
            continue
        raw_title = section.get("title") or ""
        if _is_handoff(raw_title) or _is_persona(raw_title):
            continue
        if "executive summary" in raw_title.lower():
            continue

        if _is_combined_icp_section(raw_title) or _is_icp_component(raw_title):
            buckets["icp"].append(section)
        elif _is_pillar(raw_title):
            buckets["pillars"].append(section)
        elif _is_month(raw_title):
            buckets["months"].append(section)
        elif _is_channel_section(raw_title):
            buckets["channels"].append(section)
        elif "positioning" in _clean_title(raw_title).lower():
            buckets["positioning"].append(section)
        elif any(keyword in _clean_title(raw_title).lower() for keyword in ("metrics", "risks")):
            buckets["late"].append(section)
        else:
            buckets["early"].append(section)

    buckets["pillars"].sort(key=lambda s: _pillar_sort_key(s.get("title") or ""))
    buckets["months"].sort(key=lambda s: _month_sort_key(s.get("title") or ""))
    return buckets


def render_strategy_sections(sections: list[dict[str, Any]]) -> None:
    """Render all strategy body sections with persona-style cards."""
    if not sections:
        return

    buckets = _classify_sections(sections)

    for section in buckets["early"]:
        _render_narrative_section(section)

    if buckets["icp"]:
        render_icp_section(sections)

    for section in buckets["positioning"]:
        _render_narrative_section(section)

    if buckets["pillars"]:
        render_pillars_section(sections)

    if buckets["channels"]:
        render_channels_section(sections)

    if buckets["months"]:
        render_timeline_section(sections)

    for section in buckets["late"]:
        _render_narrative_section(section)


def _render_narrative_section(section: dict[str, Any]) -> None:
    title = section.get("title") or "Section"
    body = section.get("body") or ""
    if not body.strip():
        return
    st.markdown(
        f'<div class="section-card"><div class="section-card-header">{html.escape(_clean_title(title))}</div></div>',
        unsafe_allow_html=True,
    )
    st.markdown(body)
