"""Parse and render buyer personas from Strategy Agent UI JSON."""

from __future__ import annotations

import html
import re
from typing import Any

import streamlit as st

from ui.utils.section_fields import parse_bullet_fields

NOT_SPECIFIED = "Not specified"

_COMMITTEE_PRIORITY = (
    (("decision-maker", "decision maker", "economic buyer", "budget owner"), "High"),
    (("influencer", "champion", "evaluator", "technical", "advocate", "user advocate"), "Medium"),
)
_CHANNEL_BADGES = (
    ("LinkedIn", ("linkedin",)),
    ("Webinar", ("webinar", "virtual event", "conference")),
    ("Email", ("email", "newsletter")),
    ("Sales Outreach", ("sales", "outreach", "conference", "event")),
    ("Whitepaper", ("whitepaper", "case study", "blog", "article", "forum")),
)
_JOURNEY_BY_ROLE = {
    "decision": {
        "awareness": "Executive thought leadership & industry trends",
        "consideration": "ROI webinars & peer case studies",
        "decision": "Business case review & executive demos",
        "content": "Case studies & ROI calculators",
        "channel": "LinkedIn & executive webinars",
    },
    "influencer": {
        "awareness": "Product overviews & workflow demos",
        "consideration": "Feature comparisons & pilot planning",
        "decision": "Implementation planning & vendor support review",
        "content": "How-to guides & product walkthroughs",
        "channel": "Webinars & email nurture",
    },
    "technical": {
        "awareness": "Technical blogs & architecture briefs",
        "consideration": "Integration guides & security documentation",
        "decision": "Proof of concept & technical validation",
        "content": "Technical whitepapers & API docs",
        "channel": "Blogs, forums & LinkedIn",
    },
    "default": {
        "awareness": "Educational content & market insights",
        "consideration": "Solution comparisons & demos",
        "decision": "Proof points & stakeholder alignment",
        "content": "Case studies & product content",
        "channel": "LinkedIn & webinars",
    },
}


def get_persona_field(
    persona: Any,
    possible_keys: list[str],
    default: str = NOT_SPECIFIED,
) -> str:
    """Return the first non-empty persona field matching possible keys."""
    if persona is None:
        return default
    if not isinstance(persona, dict):
        text = str(persona).strip()
        return text or default

    lowered = {str(k).lower(): v for k, v in persona.items()}
    for key in possible_keys:
        value = persona.get(key)
        if value is None:
            value = lowered.get(key.lower())
        if value is None:
            continue
        if isinstance(value, list):
            items = [str(item).strip() for item in value if str(item).strip()]
            if items:
                return "; ".join(items)
            continue
        text = str(value).strip()
        if text and text != "[]":
            return text
    return default


def _split_list_field(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if not text or text == NOT_SPECIFIED:
        return []
    parts = re.split(r"[;\n]|,\s+(?=[A-Z])", text)
    return [part.strip(" -•") for part in parts if part.strip(" -•")]


def _persona_name_from_title(title: str) -> str:
    match = re.search(r"persona\s*\d+\s*:\s*(.+)$", title, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    match = re.search(r"persona\s*:\s*(.+)$", title, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return title.strip() or NOT_SPECIFIED


def _infer_role_bucket(committee_role: str, role: str) -> str:
    combined = f"{committee_role} {role}".lower()
    if any(token in combined for token in ("decision-maker", "decision maker", "cio", "chief", "budget")):
        return "decision"
    if any(token in combined for token in ("technical", "evaluator", "architect", "engineer", "data science")):
        return "technical"
    if any(token in combined for token in ("influencer", "operations", "manager", "head of")):
        return "influencer"
    return "default"


def _infer_priority(committee_role: str, role: str, index: int) -> str:
    combined = f"{committee_role} {role}".lower()
    for keywords, priority in _COMMITTEE_PRIORITY:
        if any(keyword in combined for keyword in keywords):
            return priority
    if index == 0:
        return "High"
    if index == 1:
        return "Medium"
    return "Low"


def _normalize_channel_badge(channels_text: str) -> str:
    lowered = channels_text.lower()
    for label, keywords in _CHANNEL_BADGES:
        if any(keyword in lowered for keyword in keywords):
            return label
    return "Other"


def _priority_badge_class(priority: str) -> str:
    normalized = priority.lower()
    if normalized == "high":
        return "priority-high"
    if normalized == "low":
        return "priority-low"
    return "priority-medium"


def _normalize_persona_record(
    raw: dict[str, Any],
    *,
    fallback_name: str = NOT_SPECIFIED,
    index: int = 0,
) -> dict[str, Any]:
    role = get_persona_field(
        raw,
        ["role", "job_title", "job title", "title", "persona_role", "role_type"],
    )
    committee_role = get_persona_field(
        raw,
        ["committee_role", "role in buying committee", "buying_committee_role", "buying committee"],
    )
    goals = get_persona_field(raw, ["goals", "primary_goal", "goal"])
    pain_points = _split_list_field(
        get_persona_field(raw, ["pain_points", "pain points", "main_pain_point", "pain point"], default="")
    )
    if not pain_points:
        single_pain = get_persona_field(raw, ["main_pain_point", "pain_points", "pain points"], default="")
        pain_points = _split_list_field(single_pain)

    buying_triggers = _split_list_field(
        get_persona_field(raw, ["buying_triggers", "buying triggers"], default="")
    )
    objections = _split_list_field(get_persona_field(raw, ["objections"], default=""))
    preferred_channels = get_persona_field(
        raw,
        ["preferred_channels", "preferred channels", "recommended_channel", "channels"],
    )
    best_message = get_persona_field(
        raw,
        ["best_message", "message that would resonate", "message", "messaging_angle"],
    )
    name = get_persona_field(raw, ["name", "persona_name"], default=fallback_name)
    priority = get_persona_field(raw, ["priority"], default=_infer_priority(committee_role, role, index))
    channel_badge = get_persona_field(
        raw,
        ["recommended_channel", "best_channel"],
        default=_normalize_channel_badge(preferred_channels),
    )
    if channel_badge == NOT_SPECIFIED:
        channel_badge = _normalize_channel_badge(preferred_channels)

    role_bucket = _infer_role_bucket(committee_role, role)
    journey = _JOURNEY_BY_ROLE[role_bucket]

    return {
        "name": name,
        "role_type": role,
        "committee_role": committee_role,
        "priority": priority,
        "channel_badge": channel_badge,
        "primary_goal": goals,
        "main_pain_point": pain_points[0] if pain_points else get_persona_field(raw, ["main_pain_point"]),
        "best_message": best_message,
        "recommended_channel": preferred_channels,
        "responsibilities": get_persona_field(raw, ["responsibilities"], default=committee_role),
        "goals": goals,
        "pain_points": pain_points or [get_persona_field(raw, ["main_pain_point"])],
        "buying_triggers": buying_triggers,
        "objections": objections,
        "decision_criteria": _split_list_field(get_persona_field(raw, ["decision_criteria", "decision criteria"], default="")),
        "messaging_angle": best_message,
        "sales_enablement_notes": get_persona_field(raw, ["sales_enablement_notes", "objections"], default=NOT_SPECIFIED),
        "preferred_channels": preferred_channels,
        "awareness_stage": get_persona_field(raw, ["awareness_stage", "awareness"], default=journey["awareness"]),
        "consideration_stage": get_persona_field(
            raw,
            ["consideration_stage", "consideration"],
            default=journey["consideration"],
        ),
        "decision_stage": get_persona_field(raw, ["decision_stage", "decision"], default=journey["decision"]),
        "best_content_type": get_persona_field(
            raw,
            ["best_content_type", "content_type"],
            default=journey["content"],
        ),
        "best_channel": get_persona_field(raw, ["best_channel"], default=journey["channel"]),
    }


def _normalize_from_section(title: str, body: str, index: int) -> dict[str, Any]:
    fields = parse_bullet_fields(body)
    raw = {
        "name": _persona_name_from_title(title),
        **fields,
    }
    key_map = {
        "job title": "role",
        "role in buying committee": "committee_role",
        "goals": "goals",
        "pain points": "pain_points",
        "buying triggers": "buying_triggers",
        "preferred channels": "preferred_channels",
        "message that would resonate": "best_message",
    }
    for source, target in key_map.items():
        if source in fields:
            raw[target] = fields[source]
    return _normalize_persona_record(raw, fallback_name=_persona_name_from_title(title), index=index)


def _normalize_from_markdown(text: str) -> list[dict[str, Any]]:
    personas: list[dict[str, Any]] = []
    chunks = re.split(r"(?=^#{1,4}\s+Persona|\nPersona\s+\d+\s*:)", text, flags=re.MULTILINE | re.IGNORECASE)
    for index, chunk in enumerate(chunk for chunk in chunks if chunk.strip()):
        title_line = chunk.strip().splitlines()[0]
        title = re.sub(r"^#{1,4}\s+", "", title_line).strip()
        body = "\n".join(chunk.strip().splitlines()[1:])
        if re.search(r"persona", title, re.IGNORECASE):
            personas.append(_normalize_from_section(title, body, index))
    if personas:
        return personas

    fields = parse_bullet_fields(text)
    if fields:
        return [_normalize_persona_record(fields, index=0)]
    return []


def normalize_personas(strategy_ui: Any) -> list[dict[str, Any]]:
    """Normalize personas from Strategy Agent UI JSON into a consistent structure."""
    if not isinstance(strategy_ui, dict):
        return []

    raw_personas = strategy_ui.get("personas")
    if isinstance(raw_personas, list):
        return [
            _normalize_persona_record(item if isinstance(item, dict) else {"name": str(item)}, index=index)
            for index, item in enumerate(raw_personas)
            if item
        ]
    if isinstance(raw_personas, dict):
        return [_normalize_persona_record(raw_personas, index=0)]
    if isinstance(raw_personas, str) and raw_personas.strip():
        parsed = _normalize_from_markdown(raw_personas)
        if parsed:
            return parsed

    sections = strategy_ui.get("sections") or []
    personas: list[dict[str, Any]] = []
    for index, section in enumerate(sections):
        if not isinstance(section, dict):
            continue
        title = section.get("title") or ""
        if not re.search(r"persona\s*\d", title, re.IGNORECASE):
            continue
        personas.append(_normalize_from_section(title, section.get("body") or "", index))

    return personas


def build_buyer_journey_table(personas: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Build rows for the buyer journey table."""
    rows: list[dict[str, str]] = []
    for persona in personas:
        if not isinstance(persona, dict):
            continue
        rows.append(
            {
                "Persona": get_persona_field(persona, ["name"]),
                "Awareness Stage": get_persona_field(persona, ["awareness_stage"]),
                "Consideration Stage": get_persona_field(persona, ["consideration_stage"]),
                "Decision Stage": get_persona_field(persona, ["decision_stage"]),
                "Best Content Type": get_persona_field(persona, ["best_content_type"]),
                "Best Channel": get_persona_field(persona, ["best_channel", "recommended_channel", "preferred_channels"]),
            }
        )
    return rows


def _render_field(label: str, value: str) -> str:
    display = value if value and value != NOT_SPECIFIED else NOT_SPECIFIED
    return (
        f'<div class="persona-field">'
        f'<div class="persona-field-label">{html.escape(label)}</div>'
        f'<div class="persona-field-value">{html.escape(display)}</div>'
        f"</div>"
    )


def _build_persona_card_html(
    name: str,
    role: str,
    priority: str,
    priority_class: str,
    channel_badge: str,
    fields: list[tuple[str, str]],
) -> str:
    pieces: list[str] = [
        '<div class="persona-card">',
        '<div class="persona-card-header"><div>',
        f'<div class="persona-name">{html.escape(name)}</div>',
        f'<div class="persona-role">{html.escape(role)}</div>',
        "</div>",
        '<div class="persona-badges">',
        f'<span class="priority-badge {priority_class}">Priority: {html.escape(priority)}</span>',
        f'<span class="content-tag">Best Channel: {html.escape(channel_badge)}</span>',
        "</div></div>",
    ]
    for label, value in fields:
        pieces.append(_render_field(label, value))
    pieces.append("</div>")
    return "".join(pieces)


def _persona_display_value(persona: dict[str, Any], *keys: str, list_key: str | None = None) -> str:
    value = get_persona_field(persona, list(keys))
    if value != NOT_SPECIFIED:
        return value
    if list_key:
        items = persona.get(list_key)
        if isinstance(items, list):
            joined = "; ".join(str(item).strip() for item in items if str(item).strip())
            if joined:
                return joined
    return NOT_SPECIFIED


def render_persona_card(persona: dict[str, Any]) -> None:
    """Render a single persona snapshot card with detail expander."""
    if not isinstance(persona, dict):
        st.info("Persona data is unavailable for this entry.")
        return

    name = get_persona_field(persona, ["name"])
    role = get_persona_field(persona, ["role_type", "role"])
    committee_role = get_persona_field(persona, ["committee_role"])
    goals = _persona_display_value(persona, "goals", "primary_goal")
    pain_points = _persona_display_value(persona, "main_pain_point", "pain_points", list_key="pain_points")
    buying_triggers = _persona_display_value(persona, "buying_triggers", list_key="buying_triggers")
    preferred_channels = _persona_display_value(persona, "preferred_channels", "recommended_channel")
    best_message = get_persona_field(persona, ["best_message", "messaging_angle"])
    priority = get_persona_field(persona, ["priority"], default="Medium")
    channel_badge = get_persona_field(persona, ["channel_badge"], default="Other")

    priority_class = _priority_badge_class(priority)
    st.markdown(
        _build_persona_card_html(
            name,
            role,
            priority,
            priority_class,
            channel_badge,
            [
                ("Role in Buying Committee", committee_role),
                ("Goals", goals),
                ("Pain Points", pain_points),
                ("Buying Triggers", buying_triggers),
                ("Preferred Channels", preferred_channels),
            ],
        ),
        unsafe_allow_html=True,
    )

    with st.expander("View persona details", expanded=False):
        detail_lines = [
            ("Persona name", name),
            ("Persona role", role),
            ("Role in Buying Committee", committee_role),
            ("Goals", goals),
            ("Pain Points", pain_points),
            ("Buying Triggers", buying_triggers),
            ("Preferred Channels", preferred_channels),
            ("Message that would resonate", best_message),
        ]
        for label, value in detail_lines:
            st.markdown(f"**{label}**")
            st.markdown(value if value and value != NOT_SPECIFIED else NOT_SPECIFIED)


def render_personas_section(strategy_ui: dict[str, Any]) -> None:
    """Render the full Target Buyer Personas section."""
    personas = normalize_personas(strategy_ui)

    st.subheader("Target Buyer Personas")
    st.caption("Understand who the strategy is built for, what they care about, and how to reach them.")

    if not personas:
        st.info("No buyer personas were found in this strategy output.")
        return

    st.markdown('<div class="strategy-grid-top-spacer"></div>', unsafe_allow_html=True)
    chunk_size = 3
    for row_index, row_start in enumerate(range(0, len(personas), chunk_size)):
        if row_index > 0:
            st.markdown('<div class="strategy-grid-row-spacer"></div>', unsafe_allow_html=True)
        row_personas = personas[row_start : row_start + chunk_size]
        columns = st.columns(len(row_personas), gap="large")
        for column, persona in zip(columns, row_personas):
            with column:
                render_persona_card(persona)
    st.markdown('<div class="strategy-grid-bottom-spacer"></div>', unsafe_allow_html=True)

    st.markdown("##### Buyer Journey by Persona")
    journey_rows = build_buyer_journey_table(personas)
    if journey_rows:
        st.dataframe(journey_rows, use_container_width=True, hide_index=True)
    else:
        st.caption("Buyer journey details are not available for these personas.")
