"""Brand Alignment Agent dashboard — load, normalize, and render UI JSON."""

from __future__ import annotations

import html
import os
import re
from pathlib import Path
from typing import Any

import streamlit as st

from knowledge_base.brand_identity import ensure_logo_extracted, get_visual_system

from project_paths import OUTPUT_RUNS_DIR

ROOT_DIR = Path(__file__).resolve().parent.parent.parent

PAGE_TITLE = "Brand Alignment"
PAGE_SUBTITLE = (
    "Review how each content asset fits the brand identity, voice, and messaging standards."
)

ALIGNMENT_STATUSES = (
    "Aligned",
    "Mostly aligned",
    "Needs minor edits",
    "Needs revision",
    "Not aligned",
    "Unknown",
)

CONTENT_TYPES = ("Social Post", "Blog", "Email", "Ad", "Calendar Item", "SEO", "Other")
CHANNELS = ("LinkedIn", "Twitter", "Facebook", "Email", "Blog", "Paid Ads", "Website", "Other")

_TYPE_MAP = {
    "calendar": "Calendar Item",
    "seo": "SEO",
    "social": "Social Post",
    "blog": "Blog",
    "email": "Email",
    "ad": "Ad",
    "content_strategy": "Other",
}

_CHANNEL_MAP = {
    "calendar": "Website",
    "seo": "Website",
    "social": "LinkedIn",
    "blog": "Blog",
    "email": "Email",
    "ad": "Paid Ads",
    "content_strategy": "Other",
}

_SKIP_SECTIONS = frozenset({
    "brand guidelines summary",
    "strengths",
    "gaps",
    "recommendations",
    "executive summary",
    "executive summary of brand alignment evaluations",
    "overview",
    "brand alignment report",
    "content evaluations and scores",
})

_STATUS_CLASS = {
    "Aligned": "align-status-aligned",
    "Mostly aligned": "align-status-mostly",
    "Needs minor edits": "align-status-minor",
    "Needs revision": "align-status-revision",
    "Not aligned": "align-status-not",
    "Unknown": "align-status-unknown",
}


def load_brand_alignment_ui(run_id: str) -> dict | None:
    """Load brand_alignment.ui.json for a run."""
    path = OUTPUT_RUNS_DIR / run_id / "brand_alignment.ui.json"
    if not path.is_file():
        return None
    try:
        import json

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
            return ", ".join(str(v) for v in value[:6])
    return default


def _normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", (title or "").strip()).lower()


def _parse_bullet_section(body: str, label: str) -> list[str]:
    """Extract list items under a markdown label like **Strengths:**."""
    pattern = re.compile(
        rf"-\s*\*\*{re.escape(label)}:\*\*\s*\n((?:\s+-\s+.+\n?)*)",
        re.IGNORECASE,
    )
    match = pattern.search(body or "")
    if not match:
        return []
    items = re.findall(r"^\s+-\s+(.+)$", match.group(1), re.MULTILINE)
    return [item.strip() for item in items if item.strip()]


def _parse_scalar_field(body: str, label: str) -> str:
    match = re.search(
        rf"-\s*\*\*{re.escape(label)}:\*\*\s*(.+)",
        body or "",
        re.IGNORECASE,
    )
    return match.group(1).strip() if match else ""


def _parse_guideline_bullets(body: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in (body or "").splitlines():
        stripped = line.strip()
        if not stripped.startswith("- **"):
            continue
        match = re.match(r"^-\s*\*\*(.+?)\*\*:\s*(.*)$", stripped)
        if match:
            fields[match.group(1).strip().lower()] = match.group(2).strip()
    return fields


def _extract_brand_guidelines_text(brand_ui: dict) -> str:
    """Collect brand guideline prose from sections, output fields, or summary preview."""
    for section in brand_ui.get("sections") or []:
        if not isinstance(section, dict):
            continue
        if _normalize_title(section.get("title") or "") == "brand guidelines summary":
            body = (section.get("body") or "").strip()
            if body:
                return body

    output = _unwrap_output(brand_ui)
    for key in ("brand_guidelines_summary", "brand_guidelines"):
        candidate = output.get(key)
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
        if isinstance(candidate, dict):
            parts = [
                candidate.get("brand_voice") or "",
                candidate.get("tone") or "",
            ]
            joined = "\n".join(p for p in parts if p)
            if joined.strip():
                return joined

    raw_summary = brand_ui.get("summary") or ""
    if "brand guidelines summary" in raw_summary.lower():
        match = re.search(
            r"brand\s+guidelines\s+summary\s*(.+?)(?:\s*-\s*\*\*Content|\s*##\s|$)",
            raw_summary,
            re.IGNORECASE | re.DOTALL,
        )
        if match:
            return match.group(1).strip()

    return ""


def _infer_brand_name(parsed: dict[str, str], brand_ui: dict) -> str:
    for text in (parsed.get("positioning", ""), brand_ui.get("summary") or ""):
        match = re.search(r"\b(Beam\s*Data|BeamData)\b", text, re.IGNORECASE)
        if match:
            name = match.group(1)
            return "Beam Data" if name.lower().replace(" ", "") == "beamdata" else name.strip()

    visual = get_visual_system()
    if visual.get("doc_id", "").startswith("beam_data"):
        return "Beam Data"
    return "Not specified"


def _split_principle_chunks(text: str) -> list[str]:
    if not text:
        return []
    chunks = re.split(r"(?<=[.!?])\s+|\s*;\s*", text)
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def _coerce_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str) and value.strip():
        return [line.strip(" -•\t") for line in value.splitlines() if line.strip()]
    return []


def _unwrap_output(brand_ui: dict) -> dict:
    output = brand_ui.get("output")
    if isinstance(output, dict):
        return output
    return brand_ui


def normalize_brand_colors(brand_ui: dict) -> list[dict[str, str]]:
    """Normalize color swatches from brand UI JSON."""
    colors: list[dict[str, str]] = []

    for source in (
        brand_ui.get("colors"),
        brand_ui.get("brand_assets", {}).get("colors") if isinstance(brand_ui.get("brand_assets"), dict) else None,
        _unwrap_output(brand_ui).get("brand_visual_system", {}).get("colors")
        if isinstance(_unwrap_output(brand_ui).get("brand_visual_system"), dict)
        else None,
    ):
        if not isinstance(source, list):
            continue
        for entry in source:
            if isinstance(entry, dict):
                name = get_field(entry, ["name", "label"], default="")
                hex_val = get_field(entry, ["hex", "hex_code", "value"], default="")
                if name and name != "Not specified":
                    colors.append({"name": name, "hex": hex_val if hex_val != "Not specified" else ""})
            elif isinstance(entry, str) and entry.strip():
                colors.append({"name": entry.strip(), "hex": ""})

    if colors:
        return colors

    visual = get_visual_system()
    primary: list[dict[str, str]] = []
    secondary: list[dict[str, str]] = []
    for color in visual.get("colors") or []:
        if not isinstance(color, dict):
            continue
        item = {"name": color.get("name", ""), "hex": color.get("hex", "")}
        role = (color.get("role") or "").lower()
        if role in {"primary", "accent"}:
            primary.append(item)
        elif role in {"secondary", "background"}:
            secondary.append(item)
        else:
            primary.append(item)

    return primary + secondary


def normalize_brand_fonts(brand_ui: dict) -> list[dict[str, str]]:
    """Normalize font cards from brand UI JSON."""
    fonts: list[dict[str, str]] = []

    raw_fonts = brand_ui.get("fonts")
    if isinstance(raw_fonts, list):
        for entry in raw_fonts:
            if isinstance(entry, dict):
                fonts.append({
                    "name": get_field(entry, ["name", "family", "font"], default="Not specified"),
                    "usage": get_field(entry, ["usage", "role", "type"], default="Unknown"),
                })
            elif isinstance(entry, str) and entry.strip():
                fonts.append({"name": entry.strip(), "usage": "Unknown"})

    if fonts:
        return fonts

    output = _unwrap_output(brand_ui)
    visual = output.get("brand_visual_system") if isinstance(output.get("brand_visual_system"), dict) else {}
    if not visual:
        visual = get_visual_system()

    typo = visual.get("typography") if isinstance(visual.get("typography"), dict) else {}
    primary = typo.get("primary")
    if primary:
        fonts.append({"name": str(primary), "usage": "Heading"})
    for fallback in typo.get("fallback") or []:
        fonts.append({"name": str(fallback), "usage": "Body"})

    return fonts or [{"name": "Not specified", "usage": "Unknown"}]


def normalize_brand_guidelines(brand_ui: dict) -> dict[str, Any]:
    """Normalize brand guideline data into a consistent display format."""
    guidelines: dict[str, Any] = {
        "brand_name": "Not specified",
        "logo_path": "",
        "brand_voice": "Not specified",
        "tone": "Not specified",
        "messaging_principles": [],
        "language_to_avoid": [],
        "colors": [],
        "fonts": [],
        "primary_colors": [],
        "secondary_colors": [],
    }

    output = _unwrap_output(brand_ui)
    structured = brand_ui.get("brand_guidelines") or brand_ui.get("brand_identity")
    if not structured:
        structured = output.get("brand_guidelines")
    if not structured and isinstance(output.get("components"), dict):
        structured = output["components"].get("brand_guidelines")

    if isinstance(structured, dict):
        guidelines["brand_name"] = get_field(structured, ["brand_name", "name", "company_name"])
        guidelines["logo_path"] = get_field(structured, ["logo_path", "logo", "logo_url"], default="")
        guidelines["brand_voice"] = get_field(structured, ["brand_voice", "voice", "essence"])
        guidelines["tone"] = get_field(structured, ["tone", "brand_tone"])
        guidelines["messaging_principles"] = _coerce_list(
            structured.get("messaging_principles")
            or structured.get("content_do")
            or structured.get("preferred_terms")
        )
        guidelines["language_to_avoid"] = _coerce_list(
            structured.get("language_to_avoid")
            or structured.get("claims_to_avoid")
            or structured.get("terms_to_avoid")
            or structured.get("content_dont")
        )

    summary_text = _extract_brand_guidelines_text(brand_ui)

    if summary_text:
        parsed = _parse_guideline_bullets(summary_text)
        voice_text = parsed.get("tone and voice", "")
        if voice_text and guidelines["brand_voice"] == "Not specified":
            guidelines["brand_voice"] = voice_text
        if voice_text and guidelines["tone"] == "Not specified":
            guidelines["tone"] = voice_text

        if guidelines["brand_name"] == "Not specified":
            guidelines["brand_name"] = _infer_brand_name(parsed, brand_ui)

        guidelines["messaging_principles"].extend(_split_principle_chunks(parsed.get("messaging do's", "")))
        vocab = parsed.get("vocabulary and preferred terms", "")
        if vocab:
            guidelines["messaging_principles"].append(vocab)

        guidelines["language_to_avoid"].extend(_split_principle_chunks(parsed.get("messaging don'ts", "")))
        guidelines["language_to_avoid"].extend(_split_principle_chunks(parsed.get("claims to avoid", "")))

    visual_fallback = get_visual_system()
    if guidelines["brand_voice"] == "Not specified":
        guidelines["brand_voice"] = visual_fallback.get("essence", "Not specified")
    if guidelines["tone"] == "Not specified":
        guidelines["tone"] = visual_fallback.get("essence", "Not specified")
    if guidelines["brand_name"] == "Not specified":
        guidelines["brand_name"] = _infer_brand_name({}, brand_ui)
    if not guidelines["language_to_avoid"]:
        avoid = visual_fallback.get("avoid")
        if avoid:
            guidelines["language_to_avoid"] = _split_principle_chunks(str(avoid))

    logo = brand_ui.get("logo")
    if isinstance(logo, str) and logo.strip():
        guidelines["logo_path"] = logo.strip()
    elif isinstance(logo, dict):
        guidelines["logo_path"] = get_field(logo, ["path", "url", "filename"], default="")

    output = _unwrap_output(brand_ui)
    visual = output.get("brand_visual_system") if isinstance(output.get("brand_visual_system"), dict) else {}

    all_colors = normalize_brand_colors(brand_ui)
    guidelines["colors"] = all_colors
    primary_roles = {"primary", "accent"}
    output_visual = output.get("brand_visual_system", {})
    if isinstance(output_visual, dict) and output_visual.get("colors"):
        for color in output_visual["colors"]:
            if isinstance(color, dict):
                role = (color.get("role") or "").lower()
                item = {"name": color.get("name", ""), "hex": color.get("hex", "")}
                if role in primary_roles:
                    guidelines["primary_colors"].append(item)
                else:
                    guidelines["secondary_colors"].append(item)
    if not guidelines["primary_colors"] and not guidelines["secondary_colors"]:
        mid = max(1, len(all_colors) // 2)
        guidelines["primary_colors"] = all_colors[:mid]
        guidelines["secondary_colors"] = all_colors[mid:]

    guidelines["fonts"] = normalize_brand_fonts(brand_ui)

    guidelines["messaging_principles"] = list(dict.fromkeys(guidelines["messaging_principles"]))[:8]
    guidelines["language_to_avoid"] = list(dict.fromkeys(guidelines["language_to_avoid"]))[:8]

    return guidelines


def _map_alignment_status(raw_alignment: str, score: int | None, explicit: str = "") -> str:
    if explicit and explicit != "Not specified":
        normalized = explicit.strip().title()
        for status in ALIGNMENT_STATUSES:
            if status.lower() == normalized.lower():
                return status
        return explicit.strip()

    alignment = (raw_alignment or "").strip().lower()
    numeric = score if score is not None else -1

    if alignment == "high":
        if numeric >= 85:
            return "Aligned"
        if numeric >= 70:
            return "Mostly aligned"
        return "Needs minor edits"
    if alignment == "low":
        if numeric >= 55:
            return "Needs revision"
        return "Not aligned"
    if numeric >= 85:
        return "Aligned"
    if numeric >= 70:
        return "Mostly aligned"
    if numeric >= 55:
        return "Needs revision"
    if numeric >= 0:
        return "Not aligned"
    return "Unknown"


def _parse_section_title(title: str) -> tuple[str, str]:
    match = re.match(r"^(.+?)\s*\(([^)]+)\)\s*$", (title or "").strip())
    if match:
        return match.group(1).strip(), match.group(2).strip().lower()
    return (title or "").strip(), ""


def _item_from_evaluation(ev: dict) -> dict[str, Any]:
    raw_type = (ev.get("type") or ev.get("content_type") or "other").lower()
    content_type = _TYPE_MAP.get(raw_type, ev.get("content_type") or "Other")
    channel = ev.get("channel") or _CHANNEL_MAP.get(raw_type, "Other")

    score_raw = ev.get("alignment_score", ev.get("score"))
    score: int | None = None
    if isinstance(score_raw, (int, float)):
        score = int(score_raw)

    strengths = _coerce_list(ev.get("brand_strengths") or ev.get("strengths"))
    gaps = _coerce_list(ev.get("gaps") or ev.get("improvement_note"))
    recommendations = _coerce_list(ev.get("recommendations"))
    brand_risks = _coerce_list(ev.get("brand_risks") or ev.get("risk_category"))
    flagged = _coerce_list(ev.get("unsupported_claims") or ev.get("flagged_claims"))

    improvement = get_field(ev, ["improvement_note"], default="")
    if improvement == "Not specified" and gaps:
        improvement = gaps[0]
    if improvement == "Not specified" and recommendations:
        improvement = recommendations[0]

    return {
        "title": get_field(ev, ["title", "name"], default="Content Asset"),
        "content_type": content_type if content_type != "Not specified" else "Other",
        "channel": channel if channel != "Not specified" else "Other",
        "alignment_status": _map_alignment_status(
            str(ev.get("alignment") or ""),
            score,
            get_field(ev, ["alignment_status"], default=""),
        ),
        "alignment_score": score if score is not None else 0,
        "main_reason": get_field(ev, ["main_reason", "rationale"], default="Not specified"),
        "brand_strengths": strengths,
        "improvement_note": improvement,
        "details": {
            "brand_voice_alignment": get_field(ev, ["brand_voice_alignment"], default="Not specified"),
            "messaging_pillar_alignment": get_field(
                ev, ["messaging_pillar_alignment", "positioning_alignment"], default="Not specified"
            ),
            "tone_alignment": get_field(ev, ["tone_alignment"], default="Not specified"),
            "channel_fit": get_field(ev, ["channel_fit", "visual_fit"], default="Not specified"),
            "claim_credibility": (
                "; ".join(flagged)
                if flagged
                else get_field(ev, ["claim_credibility"], default="Not specified")
            ),
            "risk_category": ", ".join(brand_risks) if brand_risks else "Not specified",
            "recommendation": "; ".join(recommendations) if recommendations else improvement,
        },
    }


def _item_from_section(section: dict) -> dict[str, Any] | None:
    title_raw = section.get("title") or ""
    body = section.get("body") or ""
    if not body.strip():
        return None

    norm_title = _normalize_title(title_raw)
    if norm_title in _SKIP_SECTIONS:
        return None
    if not re.search(r"-\s*\*\*Score:\*\*", body, re.IGNORECASE):
        return None

    display_title, raw_type = _parse_section_title(title_raw)
    score_text = _parse_scalar_field(body, "Score")
    score: int | None = None
    if score_text.isdigit():
        score = int(score_text)

    alignment_raw = _parse_scalar_field(body, "Alignment").lower()
    strengths = _parse_bullet_section(body, "Strengths")
    gaps = _parse_bullet_section(body, "Gaps")
    recommendations = _parse_bullet_section(body, "Recommendations")
    brand_risks = _parse_bullet_section(body, "Brand risks")
    flagged = _parse_bullet_section(body, "Flagged claims in reviewed content")
    rationale = _parse_scalar_field(body, "Rationale")

    content_type = _TYPE_MAP.get(raw_type, "Other")
    channel = _CHANNEL_MAP.get(raw_type, "Other")

    improvement = gaps[0] if gaps else (recommendations[0] if recommendations else "Not specified")

    claim_cred = "; ".join(flagged) if flagged else "Not specified"
    risk_cat = "; ".join(brand_risks) if brand_risks else "Not specified"

    return {
        "title": display_title or "Content Asset",
        "content_type": content_type,
        "channel": channel,
        "alignment_status": _map_alignment_status(alignment_raw, score),
        "alignment_score": score or 0,
        "main_reason": rationale or "Not specified",
        "brand_strengths": strengths,
        "improvement_note": improvement,
        "details": {
            "brand_voice_alignment": "Not specified",
            "messaging_pillar_alignment": "Not specified",
            "tone_alignment": "Not specified",
            "channel_fit": "Not specified",
            "claim_credibility": claim_cred,
            "risk_category": risk_cat,
            "recommendation": "; ".join(recommendations) if recommendations else improvement,
        },
    }


def normalize_alignment_items(brand_ui: dict) -> list[dict[str, Any]]:
    """Normalize reviewed content assets into alignment gallery items."""
    items: list[dict[str, Any]] = []

    for key in ("alignment_items", "content_items", "evaluations"):
        raw = brand_ui.get(key)
        if not isinstance(raw, list):
            raw = _unwrap_output(brand_ui).get(key)
        if isinstance(raw, list):
            for entry in raw:
                if isinstance(entry, dict):
                    items.append(_item_from_evaluation(entry))
                elif isinstance(entry, str) and entry.strip():
                    items.append({
                        "title": entry.strip(),
                        "content_type": "Other",
                        "channel": "Other",
                        "alignment_status": "Unknown",
                        "alignment_score": 0,
                        "main_reason": "Not specified",
                        "brand_strengths": [],
                        "improvement_note": "Not specified",
                        "details": {},
                    })

    if items:
        return items

    for section in brand_ui.get("sections") or []:
        if not isinstance(section, dict):
            continue
        parsed = _item_from_section(section)
        if parsed:
            items.append(parsed)

    return items


def _resolve_logo_path(logo_path: str) -> str:
    if logo_path and logo_path != "Not specified" and os.path.isfile(logo_path):
        return logo_path
    extracted = ensure_logo_extracted()
    return extracted if os.path.isfile(extracted) else ""


def render_color_swatches(colors: list[dict[str, str]], *, label: str = "") -> None:
    if label:
        st.markdown(f"**{html.escape(label)}**")
    if not colors:
        st.caption("Not specified")
        return

    swatches = '<div class="color-swatches">'
    for color in colors:
        name = html.escape(color.get("name") or "Color")
        hex_val = color.get("hex") or ""
        chip_style = f'background:{html.escape(hex_val)}' if hex_val else "background:#e5e7eb"
        hex_html = (
            f'<span class="color-hex">{html.escape(hex_val)}</span>'
            if hex_val
            else '<span class="color-hex">—</span>'
        )
        swatches += (
            f'<div class="color-swatch">'
            f'<div class="color-chip" style="{chip_style}"></div>'
            f'<div class="color-meta"><span class="color-name">{name}</span>{hex_html}</div>'
            f"</div>"
        )
    swatches += "</div>"
    st.markdown(swatches, unsafe_allow_html=True)


def render_font_cards(fonts: list[dict[str, str]]) -> None:
    if not fonts:
        st.caption("Not specified")
        return

    cards = '<div class="brand-font-grid">'
    for font in fonts:
        name = html.escape(font.get("name") or "Not specified")
        usage = html.escape(font.get("usage") or "Unknown")
        cards += (
            f'<div class="brand-font-card">'
            f'<div class="brand-font-name">{name}</div>'
            f'<div class="brand-font-usage">{usage}</div>'
            f"</div>"
        )
    cards += "</div>"
    st.markdown(cards, unsafe_allow_html=True)


def render_brand_guidelines_header(brand_guidelines: dict[str, Any]) -> None:
    """Render the brand guidelines summary section at the top of the page."""
    st.markdown(
        '<div class="brand-guidelines-shell">'
        '<div class="section-card-header">Brand Guidelines</div></div>',
        unsafe_allow_html=True,
    )

    if (
        brand_guidelines.get("brand_voice") == "Not specified"
        and brand_guidelines.get("tone") == "Not specified"
        and not brand_guidelines.get("messaging_principles")
        and not brand_guidelines.get("colors")
    ):
        st.info("Brand guidelines were not found in structured format.")

    col_logo, col_identity = st.columns([1, 2], gap="medium")

    with col_logo:
        logo_path = _resolve_logo_path(brand_guidelines.get("logo_path", ""))
        if logo_path:
            st.image(logo_path, caption="Brand logo", use_container_width=True)
        else:
            st.markdown('<div class="logo-placeholder">B</div>', unsafe_allow_html=True)
            st.caption("Logo not available.")

    with col_identity:
        brand_name = html.escape(brand_guidelines.get("brand_name") or "Not specified")
        voice = html.escape(brand_guidelines.get("brand_voice") or "Not specified")
        tone = html.escape(brand_guidelines.get("tone") or "Not specified")

        st.markdown(
            f'<div class="brand-guideline-name">{brand_name}</div>'
            f'<div class="brand-guideline-meta">'
            f'<div class="brand-guideline-field"><span class="brand-guideline-label">Brand voice</span>'
            f'<span class="brand-guideline-value">{voice}</span></div>'
            f'<div class="brand-guideline-field"><span class="brand-guideline-label">Tone</span>'
            f'<span class="brand-guideline-value">{tone}</span></div>'
            f"</div>",
            unsafe_allow_html=True,
        )

        principles = brand_guidelines.get("messaging_principles") or []
        if principles:
            st.markdown("**Messaging principles**")
            st.markdown("\n".join(f"- {html.escape(p)}" for p in principles), unsafe_allow_html=True)
        else:
            st.markdown("**Messaging principles** — Not specified")

        avoid = brand_guidelines.get("language_to_avoid") or []
        if avoid:
            st.markdown("**Claims or language to avoid**")
            st.markdown("\n".join(f"- {html.escape(a)}" for a in avoid), unsafe_allow_html=True)

    st.markdown('<div class="brand-guideline-divider"></div>', unsafe_allow_html=True)

    c1, c2 = st.columns(2, gap="medium")
    with c1:
        render_color_swatches(
            brand_guidelines.get("primary_colors") or brand_guidelines.get("colors") or [],
            label="Primary colors",
        )
    with c2:
        render_color_swatches(brand_guidelines.get("secondary_colors") or [], label="Secondary colors")

    st.markdown("**Font types**")
    render_font_cards(brand_guidelines.get("fonts") or [])


def _extract_main_brand_risk(brand_ui: dict, items: list[dict]) -> str:
    guardrails = brand_ui.get("guardrails") or {}
    violations = guardrails.get("violations") or []
    if violations:
        return str(violations[0])

    for item in items:
        risk = item.get("details", {}).get("risk_category", "")
        if risk and risk != "Not specified":
            return risk

    for section in brand_ui.get("sections") or []:
        if not isinstance(section, dict):
            continue
        if "executive summary of brand alignment" in _normalize_title(section.get("title") or ""):
            body = section.get("body") or ""
            match = re.search(r"\*\*Common Brand Gaps:\*\*\s*\n(.+?)(?:\n\n|\*\*)", body, re.DOTALL)
            if match:
                first_line = match.group(1).strip().splitlines()[0]
                cleaned = re.sub(r"^\d+\.\s*\*\*", "", first_line).strip("* ")
                if cleaned:
                    return cleaned

    rationale = guardrails.get("rationale") or ""
    if rationale:
        return rationale[:160] + ("…" if len(rationale) > 160 else "")

    return "Not specified"


def render_alignment_summary_cards(brand_ui: dict) -> None:
    """Render summary metric cards below the brand guidelines header."""
    metrics = brand_ui.get("metrics") or {}
    items = normalize_alignment_items(brand_ui)

    overall = metrics.get("overall_score")
    overall_display = f"{overall}" if overall is not None else "Not specified"
    if overall is not None and not str(overall_display).endswith("%"):
        overall_display = f"{overall_display}"

    guardrails = brand_ui.get("guardrails") or {}
    recommendations = guardrails.get("recommendations") or []
    final_rec = recommendations[0] if recommendations else "Not specified"

    if final_rec == "Not specified":
        for section in brand_ui.get("sections") or []:
            if _normalize_title(section.get("title") or "") == "recommendations":
                recs = _coerce_list(section.get("body"))
                if recs:
                    final_rec = recs[0]
                break

    aligned = metrics.get("high_count")
    review = metrics.get("low_count")
    if aligned is None and items:
        aligned = sum(
            1 for i in items if i.get("alignment_status") in {"Aligned", "Mostly aligned"}
        )
    if review is None and items:
        review = sum(
            1
            for i in items
            if i.get("alignment_status") in {"Needs minor edits", "Needs revision", "Not aligned"}
        )

    main_risk = _extract_main_brand_risk(brand_ui, items)

    cards = [
        ("Overall Brand Alignment Score", str(overall_display)),
        ("Final Recommendation", str(final_rec)[:120] + ("…" if len(str(final_rec)) > 120 else "")),
        ("Aligned assets", str(aligned) if aligned is not None else "Not specified"),
        ("Assets needing review", str(review) if review is not None else "Not specified"),
        ("Main brand risk", str(main_risk)[:120] + ("…" if len(str(main_risk)) > 120 else "")),
    ]

    row_html = '<div class="alignment-summary-row">'
    for label, value in cards:
        row_html += (
            f'<div class="alignment-summary-card">'
            f'<div class="alignment-summary-value">{html.escape(value)}</div>'
            f'<div class="alignment-summary-label">{html.escape(label)}</div>'
            f"</div>"
        )
    row_html += "</div>"
    st.markdown(row_html, unsafe_allow_html=True)


def render_alignment_card(item: dict[str, Any], *, key_suffix: str = "") -> None:
    """Render a single content alignment gallery card."""
    title = html.escape(item.get("title") or "Content Asset")
    content_type = html.escape(item.get("content_type") or "Other")
    channel = html.escape(item.get("channel") or "Other")
    status = item.get("alignment_status") or "Unknown"
    status_cls = _STATUS_CLASS.get(status, "align-status-unknown")
    score = item.get("alignment_score")
    score_display = str(score) if score else "—"
    reason = html.escape(item.get("main_reason") or "Not specified")
    improvement = html.escape(item.get("improvement_note") or "Not specified")

    strengths = item.get("brand_strengths") or []
    strengths_html = ""
    if strengths:
        lis = "".join(f"<li>{html.escape(str(s))}</li>" for s in strengths[:4])
        strengths_html = f"<ul class='alignment-strength-list'>{lis}</ul>"

    st.markdown(
        f'<div class="content-review-card alignment-gallery-card">'
        f'<div class="content-review-header">'
        f'<div class="content-review-title">{title}</div>'
        f'<div class="content-tags">'
        f'<span class="content-tag-muted">{content_type}</span>'
        f'<span class="content-tag-muted">{channel}</span>'
        f'<span class="{status_cls}">{html.escape(status)}</span>'
        f'<span class="content-tag-muted">Score {html.escape(score_display)}</span>'
        f"</div></div>"
        f'<p class="content-card-meta"><span class="content-card-meta-label">Main reason</span>{reason}</p>'
        f"{strengths_html}"
        f'<p class="content-card-meta"><span class="content-card-meta-label">Improvement</span>{improvement}</p>'
        f"</div>",
        unsafe_allow_html=True,
    )

    details = item.get("details") or {}
    detail_rows = [
        ("Brand voice alignment", details.get("brand_voice_alignment")),
        ("Messaging pillar alignment", details.get("messaging_pillar_alignment")),
        ("Tone alignment", details.get("tone_alignment")),
        ("Visual or channel fit", details.get("channel_fit")),
        ("Claim credibility", details.get("claim_credibility")),
        ("Risky language category", details.get("risk_category")),
        ("Recommended improvement", details.get("recommendation")),
    ]
    has_details = any(v and v != "Not specified" for _, v in detail_rows)

    if has_details:
        with st.expander("View alignment details", expanded=False):
            for label, value in detail_rows:
                if value and value != "Not specified":
                    st.markdown(f"**{label}**")
                    st.markdown(str(value))


def _filter_alignment_items(
    items: list[dict[str, Any]],
    types: list[str],
    channels: list[str],
    statuses: list[str],
    score_range: tuple[int, int] | None,
) -> list[dict[str, Any]]:
    filtered = items
    if types:
        filtered = [i for i in filtered if i.get("content_type") in types]
    if channels:
        filtered = [i for i in filtered if i.get("channel") in channels]
    if statuses:
        filtered = [i for i in filtered if i.get("alignment_status") in statuses]
    if score_range:
        lo, hi = score_range
        filtered = [
            i for i in filtered
            if lo <= int(i.get("alignment_score") or 0) <= hi
        ]
    return filtered


def _render_alignment_filters(items: list[dict[str, Any]]) -> tuple[list[str], list[str], list[str], tuple[int, int] | None]:
    available_types = sorted({i["content_type"] for i in items if i.get("content_type")})
    available_channels = sorted({i["channel"] for i in items if i.get("channel")})
    available_statuses = sorted({i["alignment_status"] for i in items if i.get("alignment_status")})
    scores = [int(i.get("alignment_score") or 0) for i in items if i.get("alignment_score")]

    if not (available_types or available_channels or available_statuses or scores):
        return [], [], [], None

    st.markdown(
        '<div class="content-filter-panel"><div class="section-card-header">Filters</div></div>',
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3, gap="medium")
    with c1:
        type_filter = st.multiselect(
            "Content Type",
            options=[t for t in CONTENT_TYPES if t in available_types],
            default=[],
            key="brand_align_filter_type",
        )
    with c2:
        channel_filter = st.multiselect(
            "Channel",
            options=[c for c in CHANNELS if c in available_channels],
            default=[],
            key="brand_align_filter_channel",
        )
    with c3:
        status_filter = st.multiselect(
            "Alignment Status",
            options=[s for s in ALIGNMENT_STATUSES if s in available_statuses],
            default=[],
            key="brand_align_filter_status",
        )

    score_range: tuple[int, int] | None = None
    if scores:
        min_score, max_score = min(scores), max(scores)
        if min_score < max_score:
            selected = st.slider(
                "Score range",
                min_value=min_score,
                max_value=max_score,
                value=(min_score, max_score),
                key="brand_align_filter_score",
            )
            score_range = selected

    return type_filter, channel_filter, status_filter, score_range


def render_alignment_gallery(items: list[dict[str, Any]], *, key_prefix: str = "align") -> None:
    """Render the content alignment gallery grid."""
    if not items:
        st.warning("No content alignment items were found.")
        return

    type_filter, channel_filter, status_filter, score_range = _render_alignment_filters(items)
    filtered = _filter_alignment_items(items, type_filter, channel_filter, status_filter, score_range)

    st.markdown(
        '<div class="content-gallery-shell">'
        '<div class="content-gallery-shell-header">'
        '<div class="section-card-header">Content Alignment Gallery</div>'
        '<p class="content-gallery-caption">Review how each asset aligns with brand voice, messaging, and visual standards.</p>'
        "</div></div>",
        unsafe_allow_html=True,
    )

    if not filtered:
        st.info("No items match the current filters.")
        return

    cols_per_row = 3 if len(filtered) > 2 else 2
    for row_start in range(0, len(filtered), cols_per_row):
        row_items = filtered[row_start : row_start + cols_per_row]
        cols = st.columns(len(row_items), gap="medium")
        for col, item in zip(cols, row_items):
            with col:
                render_alignment_card(item, key_suffix=f"{key_prefix}_{row_start}")

    st.markdown('<div class="content-gallery-shell-footer"></div>', unsafe_allow_html=True)


def render_brand_alignment_page(brand_ui: dict) -> None:
    """Render the full Brand Alignment page from UI JSON."""
    status = brand_ui.get("status", "completed")
    badge = "● Review Complete" if status == "completed" else f"● Brand {status.title()}"

    st.markdown(
        f'<div class="hero-card brand-alignment-hero">'
        f'<div class="hero-top">'
        f'<div><h2 class="hero-title">{html.escape(PAGE_TITLE)}</h2>'
        f'<p class="hero-subtitle">{html.escape(PAGE_SUBTITLE)}</p></div>'
        f'<div class="hero-badge">{html.escape(badge)}</div>'
        f"</div></div>",
        unsafe_allow_html=True,
    )

    st.markdown('<div class="brand-alignment-panel">', unsafe_allow_html=True)

    guidelines = normalize_brand_guidelines(brand_ui)
    render_brand_guidelines_header(guidelines)
    render_alignment_summary_cards(brand_ui)

    items = normalize_alignment_items(brand_ui)
    render_alignment_gallery(items)

    st.markdown("</div>", unsafe_allow_html=True)

    with st.expander("Raw Brand Alignment JSON"):
        st.json(brand_ui)
