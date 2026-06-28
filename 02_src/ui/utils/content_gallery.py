"""Content Agent gallery: normalize, filter, and render content assets from UI JSON."""

from __future__ import annotations

import html
import re
from typing import Any

import streamlit as st

from ui.components.hero import render_hero
from ui.components.report_sections import render_executive_summary

CONTENT_HERO_TITLE = "Content Agent"
CONTENT_HERO_SUBTITLE = (
    "The Content Agent turns GTM strategy into ready-to-execute marketing assets. "
    "It plans calendars, SEO keywords, social posts, blogs, emails, and ad copy "
    "aligned with brand voice and target personas."
)

CONTENT_METRIC_LABELS = {
    "blog_posts": "BLOG POSTS",
    "social_posts": "SOCIAL POSTS",
    "calendar_duration": "CALENDAR",
    "total_content": "TOTAL ASSETS",
}

CONTENT_TYPES = ("Social Post", "Blog", "Email", "Ad", "Calendar Item", "Other")
CHANNELS = ("LinkedIn", "Twitter", "Facebook", "Email", "Blog", "Paid Ads", "Website", "Other")
FUNNEL_STAGES = ("Awareness", "Consideration", "Decision", "Retention", "Unknown")

TYPE_TAG_CLASS = {
    "Social Post": "tag-social",
    "Blog": "tag-blog",
    "Email": "tag-email",
    "Ad": "tag-ad",
    "Calendar Item": "tag-calendar",
    "Other": "content-tag-muted",
}

_SECTION_SKIP = frozenset({
    "content strategy summary",
    "brand and messaging guidance",
    "content priorities and handoff notes",
    "seo keywords",
    "primary keywords",
    "secondary keywords",
    "long-tail keywords",
    "search intent",
    "suggested blog topics",
    "priority ranking",
    "recommended platforms",
    "social media plan",
    "blog plan",
    "email campaign plan",
    "paid ad copy direction",
    "generated blog articles",
})

_SECTION_KEYWORDS = (
    "content", "social", "blog", "email", "ad", "calendar", "campaign", "asset",
)

_AD_FIELDS = frozenset({
    "target persona", "funnel stage", "headline", "primary text",
    "cta", "message angle", "brand alignment note",
})

_PLATFORM_RE = re.compile(r"^\d+\.\s*(LinkedIn|Twitter|Facebook)", re.IGNORECASE)
_BLOG_TOPIC_RE = re.compile(r"blog topic", re.IGNORECASE)
_POST_SECTION_RE = re.compile(r"^post\s*(\d+)$", re.IGNORECASE)
_EMAIL_SECTION_RE = re.compile(r"^email\s*(\d+)$", re.IGNORECASE)
_AD_VARIATION_RE = re.compile(r"^ad variation\s*(\d+)$", re.IGNORECASE)
_ARTICLE_SECTION_RE = re.compile(r"^article\s*(\d+)", re.IGNORECASE)
_PREVIEW_LEN = 160


def get_content_field(asset: Any, possible_keys: list[str], default: str = "Not specified") -> str:
    if not isinstance(asset, dict):
        return default if default else str(asset or "")
    lowered = {str(k).lower(): v for k, v in asset.items()}
    for key in possible_keys:
        value = lowered.get(key.lower())
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def _normalize_title(title: str) -> str:
    return re.sub(r"^\d+\.\s*", "", title or "").strip().lower()


def _clean_title(title: str) -> str:
    return re.sub(r"^\d+\.\s*", "", title or "").strip()


def _strip_markdown(text: str) -> str:
    if not text:
        return ""
    cleaned = str(text)
    cleaned = re.sub(r"^#{1,6}\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\*\*(.+?)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"\*(.+?)\*", r"\1", cleaned)
    cleaned = re.sub(r"^[-*]\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = cleaned.replace("---", " ").strip()
    return cleaned.strip().strip('"').strip("'")


def _preview(text: str, limit: int = _PREVIEW_LEN) -> str:
    text = _strip_markdown(text)
    text = re.sub(r"\s+", " ", (text or "").strip())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _normalize_funnel(value: str) -> str:
    if not value or not value.strip():
        return "Unknown"
    lowered = value.lower()
    for stage in FUNNEL_STAGES[:-1]:
        if stage.lower() in lowered:
            return stage
    return "Unknown"


def _detect_channel(*texts: str, default: str = "Other") -> str:
    combined = " ".join(t for t in texts if t).lower()
    if "linkedin" in combined:
        return "LinkedIn"
    if "twitter" in combined or " x.com" in combined or combined.strip() == "x":
        return "Twitter"
    if "facebook" in combined:
        return "Facebook"
    if "paid ad" in combined or re.search(r"\bad\b", combined):
        return "Paid Ads"
    if "email" in combined or "newsletter" in combined:
        return "Email"
    if "blog" in combined or "article" in combined:
        return "Blog"
    if "website" in combined or "webinar" in combined:
        return "Website"
    return default


def _parse_md_fields(body: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in (body or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        match = re.match(r"^[-*]\s+\*\*(.+?):\*\*\s*(.*)$", stripped)
        if not match:
            match = re.match(r"^[-*]\s+\*\*(.+?)\*\*:?\s*(.*)$", stripped)
        if match:
            fields[match.group(1).strip().lower().rstrip(":")] = match.group(2).strip()
    return fields


def _parse_content_fields(body: str) -> dict[str, str]:
    """Parse bullet and inline **Label:** value fields from content sections."""
    fields = _parse_md_fields(body or "")
    for match in re.finditer(
        r"\*\*(.+?)\*\*:?\s*(.*?)(?=\n\s*\*\*[^*]+\*\*:?|\Z)",
        body or "",
        flags=re.DOTALL,
    ):
        key = match.group(1).strip().lower().rstrip(":")
        value = match.group(2).strip().rstrip("-").strip()
        if value:
            fields[key] = value
    return fields


def _section_number(raw_title: str, default: str = "1") -> str:
    match = re.search(r"(\d+)", raw_title or "")
    return match.group(1) if match else default


def _asset_from_post_section(raw_title: str, body: str) -> dict[str, str]:
    fields = _parse_content_fields(body)
    num = _section_number(raw_title)
    platform = fields.get("platform", "")
    channel = _map_channel(platform) if platform else "Other"
    post_title = _strip_markdown(fields.get("title", "")).strip('"')
    copy = fields.get("full post copy") or fields.get("sample post copy") or ""
    label = f"{channel} Post {num}" if channel != "Other" else f"Post {num}"
    return _make_asset(
        title=label,
        content_type="Social Post",
        channel=channel,
        funnel_stage=fields.get("funnel stage", "Unknown"),
        target_persona=fields.get("target persona", ""),
        message_pillar=post_title,
        preview=_preview(copy),
        full_content=body,
        cta=fields.get("cta", "").strip('"'),
        notes=fields.get("brand alignment note", ""),
    )


def _asset_from_email_section(raw_title: str, body: str) -> dict[str, str]:
    fields = _parse_content_fields(body)
    num = _section_number(raw_title)
    subject = fields.get("subject line", f"Email {num}").strip('"')
    summary = fields.get("preview text") or fields.get("email body summary") or fields.get("email body") or ""
    return _make_asset(
        title=subject,
        content_type="Email",
        channel="Email",
        funnel_stage=fields.get("funnel stage", "Unknown"),
        target_persona=fields.get("target persona", ""),
        objective=fields.get("email objective", ""),
        preview=_preview(summary),
        full_content=body,
        cta=fields.get("cta", "").strip('"'),
        notes=fields.get("brand alignment note", ""),
    )


def _asset_from_ad_variation_section(raw_title: str, body: str) -> dict[str, str]:
    fields = _parse_content_fields(body)
    num = _section_number(raw_title)
    platform = fields.get("platform", "")
    channel = _map_channel(platform) if platform else "Paid Ads"
    headline = fields.get("headline", f"Ad Variation {num}").strip('"')
    primary = fields.get("primary text", "")
    return _make_asset(
        title=headline,
        content_type="Ad",
        channel=channel if channel != "Other" else "Paid Ads",
        funnel_stage=fields.get("funnel stage", "Unknown"),
        target_persona=fields.get("target persona", ""),
        preview=_preview(primary or body),
        full_content=body,
        cta=fields.get("cta", "").strip('"'),
        notes=fields.get("brand alignment note", ""),
    )


def _asset_from_article_section(raw_title: str, body: str) -> dict[str, str]:
    fields = _parse_content_fields(body)
    title = _clean_title(raw_title)
    if re.match(r"^article\s*\d+\s*:", title, re.IGNORECASE):
        title = title.split(":", 1)[1].strip()
    intro = ""
    intro_match = re.search(r"####\s*Introduction\s*\n+(.*?)(?=\n####|\Z)", body, re.DOTALL | re.IGNORECASE)
    if intro_match:
        intro = intro_match.group(1).strip()
    return _make_asset(
        title=title,
        content_type="Blog",
        channel="Blog",
        funnel_stage=fields.get("funnel stage", "Unknown"),
        target_persona=fields.get("target persona", ""),
        preview=_preview(intro or body),
        full_content=body,
        cta=fields.get("cta", "").strip('"'),
    )


def _extract_post_theme(full_content: str) -> str:
    fields = _parse_content_fields(full_content)
    if fields.get("title"):
        return _strip_markdown(fields["title"]).strip('"')
    match = re.search(r"Post Idea\s*\d+:\s*(.+?)(?:\n|$)", full_content or "", re.IGNORECASE)
    if match:
        return _strip_markdown(match.group(1).strip())
    header = re.search(r"^#{1,6}\s*(.+?)(?:\n|$)", full_content or "", re.MULTILINE)
    if header:
        title = header.group(1).strip()
        if ":" in title:
            return _strip_markdown(title.split(":", 1)[1].strip())
        return _strip_markdown(title)
    return ""


def _build_card_preview_html(asset: dict[str, str]) -> str:
    content_type = asset.get("content_type", "")
    full_content = asset.get("full_content") or ""
    fields = _parse_content_fields(full_content)
    parts: list[str] = []

    if content_type == "Social Post":
        theme = (
            _strip_markdown(fields.get("title", "")).strip('"')
            or asset.get("message_pillar", "")
            or _extract_post_theme(full_content)
        )
        copy = fields.get("full post copy") or fields.get("sample post copy") or asset.get("preview") or ""
        copy = _strip_markdown(copy).strip('"')
        if theme:
            parts.append(f'<div class="content-card-theme">{html.escape(theme)}</div>')
        if theme and copy:
            parts.append('<div class="content-card-divider"></div>')
        if copy:
            parts.append(
                f'<p class="content-snippet content-card-copy">"{html.escape(_preview(copy, 200))}"</p>'
            )
        persona = fields.get("target persona") or asset.get("target_persona") or ""
        if persona:
            persona = _strip_markdown(persona).strip("- ")
            parts.append(
                f'<p class="content-card-meta">'
                f'<span class="content-card-meta-label">Persona</span> '
                f"{html.escape(persona)}</p>"
            )
    elif content_type == "Email":
        subject = fields.get("subject line") or asset.get("title") or ""
        summary = (
            fields.get("preview text")
            or fields.get("email body summary")
            or fields.get("email body")
            or asset.get("preview")
            or ""
        )
        if subject:
            parts.append(
                f'<div class="content-card-theme">{html.escape(_strip_markdown(subject).strip(chr(34)))}</div>'
            )
        if subject and summary:
            parts.append('<div class="content-card-divider"></div>')
        if summary:
            parts.append(f'<p class="content-snippet">{html.escape(_preview(_strip_markdown(summary)))}</p>')
    elif content_type == "Ad":
        headline = fields.get("headline") or asset.get("title") or ""
        primary = fields.get("primary text") or asset.get("preview") or ""
        if headline:
            parts.append(
                f'<div class="content-card-theme">{html.escape(_strip_markdown(headline).strip(chr(34)))}</div>'
            )
        if headline and primary:
            parts.append('<div class="content-card-divider"></div>')
        if primary:
            parts.append(f'<p class="content-snippet">{html.escape(_preview(_strip_markdown(primary)))}</p>')
    elif content_type == "Blog":
        theme = asset.get("title") or ""
        keyword = fields.get("target keyword") or ""
        if theme:
            parts.append(f'<div class="content-card-theme">{html.escape(_strip_markdown(theme))}</div>')
        if keyword:
            if theme:
                parts.append('<div class="content-card-divider"></div>')
            parts.append(
                f'<p class="content-card-meta">'
                f'<span class="content-card-meta-label">Keyword</span> '
                f"{html.escape(_strip_markdown(keyword))}</p>"
            )
        outline = asset.get("preview") or ""
        if outline and not keyword:
            if theme:
                parts.append('<div class="content-card-divider"></div>')
            parts.append(f'<p class="content-snippet">{html.escape(_preview(_strip_markdown(outline)))}</p>')
    elif content_type == "Calendar Item":
        preview = asset.get("preview") or ""
        objective = asset.get("objective") or fields.get("objective") or ""
        if preview:
            parts.append(f'<div class="content-card-theme">{html.escape(_strip_markdown(preview))}</div>')
        if objective:
            if preview:
                parts.append('<div class="content-card-divider"></div>')
            parts.append(f'<p class="content-snippet">{html.escape(_preview(_strip_markdown(objective)))}</p>')
    else:
        preview = _strip_markdown(asset.get("preview") or full_content)
        if preview:
            parts.append(f'<p class="content-snippet">{html.escape(_preview(preview))}</p>')

    if parts:
        return "".join(parts)
    fallback = _strip_markdown(asset.get("preview") or full_content)
    return f'<p class="content-snippet">{html.escape(_preview(fallback))}</p>'


def _make_asset(
    *,
    title: str,
    content_type: str,
    channel: str = "Other",
    funnel_stage: str = "Unknown",
    target_persona: str = "",
    message_pillar: str = "",
    objective: str = "",
    preview: str = "",
    full_content: str = "",
    cta: str = "",
    notes: str = "",
    status: str = "",
) -> dict[str, str]:
    full = full_content or preview or title
    return {
        "title": title or content_type,
        "content_type": content_type if content_type in CONTENT_TYPES else "Other",
        "channel": channel if channel in CHANNELS else "Other",
        "funnel_stage": _normalize_funnel(funnel_stage),
        "target_persona": target_persona.strip() if target_persona else "",
        "message_pillar": message_pillar.strip() if message_pillar else "",
        "objective": objective.strip() if objective else "",
        "preview": preview or _preview(full),
        "full_content": full,
        "cta": cta.strip() if cta else "",
        "notes": notes.strip() if notes else "",
        "status": status.strip() if status else "",
    }


def _asset_from_dict(raw: dict[str, Any], default_type: str = "Other") -> dict[str, str]:
    title = get_content_field(
        raw,
        ["title", "name", "theme", "headline", "subject", "subject_line", "topic"],
        default="",
    )
    content_type = get_content_field(
        raw,
        ["content_type", "type", "format", "content format"],
        default=default_type,
    )
    if content_type == "Not specified":
        content_type = default_type
    body = get_content_field(
        raw,
        ["full_content", "body", "text", "copy", "content", "primary_text", "primary text", "sample"],
        default="",
    )
    if body == "Not specified":
        body = ""
    return _make_asset(
        title=title if title != "Not specified" else default_type,
        content_type=_map_content_type(content_type),
        channel=_map_channel(get_content_field(raw, ["channel", "platform"], default="Other")),
        funnel_stage=get_content_field(raw, ["funnel_stage", "funnel stage", "stage"], default="Unknown"),
        target_persona=get_content_field(raw, ["target_persona", "target persona", "persona"], default=""),
        message_pillar=get_content_field(
            raw, ["message_pillar", "message pillar", "message_angle", "message angle"], default="",
        ),
        objective=get_content_field(raw, ["objective", "email objective", "goal"], default=""),
        preview=get_content_field(raw, ["preview", "hook", "preview_text", "preview text"], default=""),
        full_content=body,
        cta=get_content_field(raw, ["cta", "call_to_action"], default=""),
        notes=get_content_field(raw, ["notes", "brand alignment note", "brand_alignment_note"], default=""),
        status=get_content_field(raw, ["status", "tag"], default=""),
    )


def _map_content_type(value: str) -> str:
    lowered = (value or "").lower()
    if "social" in lowered or "post" in lowered:
        return "Social Post"
    if "blog" in lowered:
        return "Blog"
    if "email" in lowered:
        return "Email"
    if "ad" in lowered or "paid" in lowered:
        return "Ad"
    if "calendar" in lowered:
        return "Calendar Item"
    return "Other"


def _map_channel(value: str) -> str:
    if value == "Not specified":
        return "Other"
    lowered = value.lower()
    if "twitter" in lowered:
        return "Twitter"
    if "facebook" in lowered:
        return "Facebook"
    if "linkedin" in lowered:
        return "LinkedIn"
    for channel in CHANNELS:
        if channel.lower() in lowered:
            return channel
    return "Other"


def _parse_calendar_rows(body: str) -> list[dict[str, str]]:
    lines = [
        line for line in (body or "").splitlines()
        if line.strip().startswith("|") and not re.match(r"^\|[-\s|:]+\|$", line.strip())
    ]
    if len(lines) < 2:
        return []
    headers = [h.strip().lower() for h in lines[0].split("|")[1:-1]]
    rows: list[dict[str, str]] = []
    for line in lines[1:]:
        cells = [c.strip() for c in line.split("|")[1:-1]]
        if len(cells) != len(headers):
            continue
        rows.append(dict(zip(headers, cells)))
    return rows


def _calendar_duration_from_sections(sections: list[dict[str, Any]]) -> str:
    for section in sections:
        title = section.get("title") or ""
        match = re.search(r"(\d+)\s*[- ]?\s*day", title, re.IGNORECASE)
        if match:
            days = match.group(1)
            return f"{days} days"
    max_day = 0
    for section in sections:
        if "calendar" not in (section.get("title") or "").lower():
            continue
        for row in _parse_calendar_rows(section.get("body") or ""):
            day_val = row.get("day", "")
            day_match = re.search(r"\d+", str(day_val))
            if day_match:
                max_day = max(max_day, int(day_match.group()))
    if max_day:
        return f"{max_day} days"
    return ""


def _split_social_posts(body: str, platform: str) -> list[dict[str, str]]:
    assets: list[dict[str, str]] = []
    chunks = re.split(r"(?=(?:####\s*|\*\*)Post Idea\s*\d+)", body or "", flags=re.IGNORECASE)
    if len(chunks) <= 1:
        chunks = re.split(r"\n-{3,}\s*\n", body or "")
    for index, chunk in enumerate(chunks, start=1):
        chunk = chunk.strip()
        if not chunk:
            continue
        idea = re.search(r"Post Idea\s*(\d+)", chunk, re.IGNORECASE)
        label = f"{platform} Post {idea.group(1)}" if idea else f"{platform} Post {index}"
        fields = _parse_content_fields(chunk)
        copy = fields.get("full post copy") or fields.get("sample post copy") or ""
        if not copy:
            copy = chunk
        theme = _strip_markdown(fields.get("title", "")).strip('"') or _extract_post_theme(chunk)
        assets.append(
            _make_asset(
                title=label,
                content_type="Social Post",
                channel=_map_channel(platform),
                funnel_stage=fields.get("funnel stage", "Unknown"),
                target_persona=fields.get("target persona", ""),
                message_pillar=theme,
                objective=fields.get("objective", ""),
                preview=_preview(copy if copy != chunk else theme or copy),
                full_content=chunk,
                cta=fields.get("cta", "").strip('"'),
                notes=fields.get("brand alignment note", ""),
            )
        )
    return assets


def _split_emails(body: str) -> list[dict[str, str]]:
    assets: list[dict[str, str]] = []
    parts = re.split(r"(?=(?:####\s*Email\s*\d+|\d+\.\s+\*\*Email\s*\d+\*\*))", body or "", flags=re.IGNORECASE)
    for part in parts:
        part = part.strip()
        if not part or not re.search(r"email\s*\d+", part, re.IGNORECASE):
            continue
        title_match = re.search(r"(?:####\s*Email\s*\d+:\s*(.+)|\d+\.\s+\*\*Email\s*(\d+)\*\*)", part, re.IGNORECASE)
        if title_match:
            title = (title_match.group(1) or f"Email {title_match.group(2)}").strip()
        else:
            title = "Email"
        fields = _parse_content_fields(part)
        summary = fields.get("email body summary", part)
        assets.append(
            _make_asset(
                title=fields.get("subject line", title).strip('"'),
                content_type="Email",
                channel="Email",
                funnel_stage=fields.get("funnel stage", "Unknown"),
                target_persona=fields.get("target persona", ""),
                message_pillar="",
                objective=fields.get("email objective", ""),
                preview=_preview(summary),
                full_content=part,
                cta=fields.get("cta", ""),
                notes=fields.get("brand alignment note", ""),
            )
        )
    return assets


def _split_blog_articles(body: str) -> list[dict[str, str]]:
    assets: list[dict[str, str]] = []
    for match in re.finditer(
        r"[-*]\s+\*\*(?:Article Title|)(.+?)\*\*\s*(?:-\s*Summary:\s*)?(.+?)(?=\n[-*]\s+\*\*|\Z)",
        body or "",
        re.DOTALL,
    ):
        title = match.group(1).strip().strip(":")
        summary = match.group(2).strip()
        assets.append(
            _make_asset(
                title=title,
                content_type="Blog",
                channel="Blog",
                preview=_preview(summary),
                full_content=summary,
            )
        )
    numbered = re.findall(r"\d+\.\s+\*\*(.+?)\*\*\s*-\s*(.+)", body or "")
    for title, summary in numbered:
        assets.append(
            _make_asset(
                title=title.strip(),
                content_type="Blog",
                channel="Blog",
                preview=_preview(summary),
                full_content=summary,
            )
        )
    return assets


def _ad_groups_from_sections(sections: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        title = _normalize_title(section.get("title") or "")
        if title in _AD_FIELDS:
            current.append(section)
            continue
        if current:
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    return groups


def _asset_from_ad_group(group: list[dict[str, Any]], index: int) -> dict[str, str]:
    fields = {
        _normalize_title(s.get("title") or ""): (s.get("body") or "").strip()
        for s in group
    }
    headline = fields.get("headline", "").strip('"')
    persona = fields.get("target persona", "").strip("- ").strip()
    primary = fields.get("primary text", "")
    parts = [f"**Headline:** {headline}", f"**Primary Text:** {primary}"]
    if fields.get("message angle"):
        parts.append(f"**Message Angle:** {fields['message angle']}")
    full = "\n\n".join(parts)
    return _make_asset(
        title=headline or f"Ad Variant {index}",
        content_type="Ad",
        channel="Paid Ads",
        funnel_stage=fields.get("funnel stage", "Unknown"),
        target_persona=persona,
        message_pillar=fields.get("message angle", ""),
        preview=_preview(primary or headline),
        full_content=full,
        cta=fields.get("cta", "").strip('"'),
        notes=fields.get("brand alignment note", ""),
    )


def extract_assets_from_sections(content_ui: dict[str, Any]) -> list[dict[str, str]]:
    sections = content_ui.get("sections") or []
    if not isinstance(sections, list):
        return []

    assets: list[dict[str, str]] = []
    seen_titles: set[str] = set()
    calendar_keys: set[str] = set()

    def _add(asset: dict[str, str]) -> None:
        if asset.get("content_type") == "Calendar Item":
            cal_key = "|".join(
                asset.get(field, "") for field in ("title", "channel", "target_persona", "cta")
            )
            if cal_key in calendar_keys:
                return
            calendar_keys.add(cal_key)
        key = f"{asset['title']}|{asset['content_type']}|{asset['preview'][:80]}"
        if key in seen_titles:
            return
        seen_titles.add(key)
        assets.append(asset)

    calendar_sections = [
        s for s in sections
        if isinstance(s, dict) and "calendar" in (s.get("title") or "").lower()
        and "|" in (s.get("body") or "")
    ]
    best_calendar = max(
        calendar_sections,
        key=lambda s: len(_parse_calendar_rows(s.get("body") or "")),
        default=None,
    )
    if best_calendar:
        body = best_calendar.get("body") or ""
        for row in _parse_calendar_rows(body):
            topic = row.get("topic") or row.get("content type") or "Calendar Item"
            day = row.get("day", "")
            platform = row.get("platform", "")
            _add(
                _make_asset(
                    title=f"Day {day}: {topic}".strip(": ") if day else str(topic),
                    content_type="Calendar Item",
                    channel=_detect_channel(platform, row.get("format", "")),
                    funnel_stage=row.get("funnel stage", "Unknown"),
                    target_persona=row.get("target persona", ""),
                    objective=row.get("objective", ""),
                    preview=_preview(str(topic)),
                    full_content="\n".join(f"**{k.title()}:** {v}" for k, v in row.items() if v),
                    cta=row.get("cta", "").strip('"'),
                    notes=row.get("brand alignment note", ""),
                )
            )

    for section in sections:
        if not isinstance(section, dict):
            continue
        raw_title = section.get("title") or ""
        norm = _normalize_title(raw_title)
        body = (section.get("body") or "").strip()
        if not body:
            continue
        if norm in _SECTION_SKIP:
            continue
        if re.search(r"seo\s+keywords?", norm):
            continue
        if section is best_calendar:
            continue
        if _POST_SECTION_RE.match(norm):
            _add(_asset_from_post_section(raw_title, body))
            continue
        if _EMAIL_SECTION_RE.match(norm):
            _add(_asset_from_email_section(raw_title, body))
            continue
        if _AD_VARIATION_RE.match(norm):
            _add(_asset_from_ad_variation_section(raw_title, body))
            continue
        if _ARTICLE_SECTION_RE.match(norm):
            _add(_asset_from_article_section(raw_title, body))
            continue
        if not any(kw in norm for kw in _SECTION_KEYWORDS) and not _PLATFORM_RE.match(raw_title):
            if norm not in _AD_FIELDS and norm not in {"campaign objective", "4-email sequence", "email sequence"}:
                continue

        if "calendar" in norm and "|" in body:
            continue

        if _PLATFORM_RE.match(raw_title):
            platform = _PLATFORM_RE.match(raw_title).group(1)
            for asset in _split_social_posts(body, platform):
                _add(asset)
            continue

        if _BLOG_TOPIC_RE.search(raw_title):
            fields = _parse_md_fields(body)
            title = _clean_title(raw_title)
            if ":" in title:
                title = title.split(":", 1)[1].strip().strip('"')
            _add(
                _make_asset(
                    title=title,
                    content_type="Blog",
                    channel="Blog",
                    funnel_stage=fields.get("funnel stage", "Unknown"),
                    target_persona=fields.get("target persona", ""),
                    message_pillar=fields.get("why this blog supports the gtm strategy", ""),
                    objective=fields.get("why this blog supports the gtm strategy", ""),
                    preview=_preview(body),
                    full_content=body,
                    cta=fields.get("cta", "").strip('"'),
                )
            )
            continue

        if norm in {"4-email sequence", "email sequence"}:
            for asset in _split_emails(body):
                _add(asset)
            continue

        if norm == "campaign objective":
            _add(
                _make_asset(
                    title="Campaign Objective",
                    content_type="Other",
                    channel="Other",
                    preview=_preview(body),
                    full_content=body,
                    objective=body,
                )
            )
            continue

        if "generated blog" in norm:
            for asset in _split_blog_articles(body):
                _add(asset)
            continue

        if norm == "paid ad copy direction" or ("ad" in norm and "copy" in norm):
            fields = _parse_md_fields(body)
            _add(
                _make_asset(
                    title=fields.get("headline", "Paid Ad Copy").strip('"'),
                    content_type="Ad",
                    channel=_detect_channel(body, default="Paid Ads"),
                    funnel_stage=fields.get("funnel stage", "Unknown"),
                    target_persona=fields.get("target persona", ""),
                    preview=_preview(fields.get("primary text", body)),
                    full_content=body,
                    cta=fields.get("cta", "").strip('"'),
                )
            )
            continue

        _add(
            _make_asset(
                title=_clean_title(raw_title),
                content_type=_map_content_type(norm),
                channel=_detect_channel(raw_title, body),
                preview=_preview(body),
                full_content=body,
            )
        )

    for index, group in enumerate(_ad_groups_from_sections(sections), start=1):
        _add(_asset_from_ad_group(group, index))

    return assets


def _assets_from_social_posts(social: Any) -> list[dict[str, str]]:
    assets: list[dict[str, str]] = []
    if isinstance(social, str):
        return [_make_asset(title="Social Posts", content_type="Social Post", channel="Other", full_content=social)]
    if not isinstance(social, dict):
        return assets
    for platform, posts in social.items():
        channel = _map_channel(str(platform))
        if isinstance(posts, list):
            for i, post in enumerate(posts, 1):
                if isinstance(post, dict):
                    assets.append(_asset_from_dict(post, default_type="Social Post"))
                    assets[-1]["channel"] = channel
                    if assets[-1]["title"] in ("Social Post", "Not specified"):
                        assets[-1]["title"] = f"{platform.title()} Post {i}"
                elif post:
                    assets.append(
                        _make_asset(
                            title=f"{platform.title()} Post {i}",
                            content_type="Social Post",
                            channel=channel,
                            full_content=str(post),
                        )
                    )
        elif posts:
            assets.append(
                _make_asset(
                    title=f"{platform.title()} Posts",
                    content_type="Social Post",
                    channel=channel,
                    full_content=str(posts),
                )
            )
    return assets


def _assets_from_blog_plan(blog: Any) -> list[dict[str, str]]:
    if isinstance(blog, str):
        return [_make_asset(title="Blog Plan", content_type="Blog", channel="Blog", full_content=blog)]
    if isinstance(blog, dict):
        return [
            _make_asset(
                title=str(title),
                content_type="Blog",
                channel="Blog",
                full_content=str(body),
            )
            for title, body in blog.items()
        ]
    if isinstance(blog, list):
        return [_asset_from_dict(item, "Blog") for item in blog if isinstance(item, dict)]
    return []


def _assets_from_list_or_dict(items: Any, content_type: str, channel: str) -> list[dict[str, str]]:
    assets: list[dict[str, str]] = []
    if isinstance(items, str):
        return [_make_asset(title=content_type, content_type=content_type, channel=channel, full_content=items)]
    if isinstance(items, dict):
        for key, value in items.items():
            if isinstance(value, dict):
                asset = _asset_from_dict(value, content_type)
                if asset["title"] in (content_type, "Not specified"):
                    asset["title"] = str(key)
                assets.append(asset)
            else:
                assets.append(
                    _make_asset(
                        title=str(key),
                        content_type=content_type,
                        channel=channel,
                        full_content=str(value),
                    )
                )
    elif isinstance(items, list):
        for i, item in enumerate(items, 1):
            if isinstance(item, dict):
                asset = _asset_from_dict(item, content_type)
                if asset["title"] in (content_type, "Not specified"):
                    asset["title"] = f"{content_type} {i}"
                assets.append(asset)
            elif item:
                assets.append(
                    _make_asset(
                        title=f"{content_type} {i}",
                        content_type=content_type,
                        channel=channel,
                        full_content=str(item),
                    )
                )
    return assets


def normalize_content_assets(content_ui: dict[str, Any]) -> list[dict[str, str]]:
    if not isinstance(content_ui, dict):
        return []

    assets: list[dict[str, str]] = []

    for key in ("content_assets", "assets"):
        raw = content_ui.get(key)
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict):
                    assets.append(_asset_from_dict(item))
                elif isinstance(item, str) and item.strip():
                    assets.append(_make_asset(title="Content Asset", content_type="Other", full_content=item))

    assets.extend(_assets_from_social_posts(content_ui.get("social_posts")))
    assets.extend(_assets_from_blog_plan(content_ui.get("blog_plan") or content_ui.get("blog_posts")))
    assets.extend(_assets_from_list_or_dict(content_ui.get("email_campaign"), "Email", "Email"))
    assets.extend(_assets_from_list_or_dict(content_ui.get("ad_copy"), "Ad", "Paid Ads"))

    calendar = content_ui.get("content_calendar")
    if calendar:
        if isinstance(calendar, str):
            for row in _parse_calendar_rows(calendar):
                topic = row.get("topic", "Calendar Item")
                assets.append(
                    _make_asset(
                        title=str(topic),
                        content_type="Calendar Item",
                        channel=_detect_channel(row.get("platform", "")),
                        funnel_stage=row.get("funnel stage", "Unknown"),
                        target_persona=row.get("target persona", ""),
                        full_content=str(row),
                    )
                )
        elif isinstance(calendar, list):
            for item in calendar:
                if isinstance(item, dict):
                    assets.append(_asset_from_dict(item, "Calendar Item"))

    output = content_ui.get("output")
    if isinstance(output, dict):
        components = output.get("components")
        if isinstance(components, list):
            for comp in components:
                if isinstance(comp, dict):
                    assets.append(_asset_from_dict(comp))

    section_assets = extract_assets_from_sections(content_ui)
    assets.extend(section_assets)

    deduped: list[dict[str, str]] = []
    seen: set[str] = set()
    for asset in assets:
        key = f"{asset['title']}|{asset['content_type']}|{asset['preview'][:60]}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(asset)
    return deduped


_CALENDAR_TABLE_COLUMNS = (
    ("day", "Day"),
    ("platform", "Platform"),
    ("content type", "Content Type"),
    ("format", "Format"),
    ("topic", "Topic"),
    ("target persona", "Target Persona"),
    ("funnel stage", "Funnel Stage"),
    ("objective", "Objective"),
    ("cta", "CTA"),
    ("brand alignment note", "Brand Alignment"),
)


def extract_calendar_table_rows(content_ui: dict[str, Any]) -> list[dict[str, str]]:
    """Return parsed calendar rows from the richest calendar source in UI JSON."""
    best_rows: list[dict[str, str]] = []
    sections = content_ui.get("sections") or []

    calendar_sections = [
        s for s in sections
        if isinstance(s, dict) and "calendar" in (s.get("title") or "").lower()
        and "|" in (s.get("body") or "")
    ]
    if calendar_sections:
        best_section = max(
            calendar_sections,
            key=lambda s: len(_parse_calendar_rows(s.get("body") or "")),
        )
        best_rows = _parse_calendar_rows(best_section.get("body") or "")

    calendar = content_ui.get("content_calendar")
    if isinstance(calendar, str) and "|" in calendar:
        rows = _parse_calendar_rows(calendar)
        if len(rows) > len(best_rows):
            best_rows = rows

    def _day_sort(row: dict[str, str]) -> int:
        match = re.search(r"\d+", str(row.get("day", "")))
        return int(match.group()) if match else 9999

    return sorted(best_rows, key=_day_sort)


def render_content_calendar_table(rows: list[dict[str, str]]) -> None:
    if not rows:
        return

    active_columns = [
        (key, label)
        for key, label in _CALENDAR_TABLE_COLUMNS
        if any((row.get(key) or "").strip() for row in rows)
    ]
    if not active_columns:
        return

    st.markdown(
        '<div class="content-calendar-shell">'
        '<div class="section-card-header">Content Calendar</div>'
        '<p class="content-gallery-caption">Scheduled content across channels and funnel stages.</p>'
        "</div>",
        unsafe_allow_html=True,
    )

    table_rows = [
        {label: (row.get(key) or "").strip() for key, label in active_columns}
        for row in rows
    ]
    st.dataframe(table_rows, use_container_width=True, hide_index=True)


def gallery_assets_only(assets: list[dict[str, str]]) -> list[dict[str, str]]:
    return [asset for asset in assets if asset.get("content_type") != "Calendar Item"]


def derive_content_gallery_metrics(
    assets: list[dict[str, str]],
    content_ui: dict[str, Any],
) -> dict[str, str]:
    blog = sum(1 for a in assets if a.get("content_type") == "Blog")
    social = sum(1 for a in assets if a.get("content_type") == "Social Post")
    total = len(assets)
    duration = _calendar_duration_from_sections(content_ui.get("sections") or [])
    if not duration:
        cal_items = sum(1 for a in assets if a.get("content_type") == "Calendar Item")
        if cal_items:
            duration = f"{cal_items} items"
    return {
        "blog_posts": str(blog) if blog else "—",
        "social_posts": str(social) if social else "—",
        "calendar_duration": duration or "—",
        "total_content": str(total) if total else "—",
    }


def _tag_class(content_type: str) -> str:
    return TYPE_TAG_CLASS.get(content_type, "content-tag-muted")


_FIELD_LABELS = {
    "sample post copy": "Post copy",
    "full post copy": "Post copy",
    "target persona": "Target persona",
    "funnel stage": "Funnel stage",
    "message angle": "Message angle",
    "brand alignment note": "Brand alignment",
    "subject line": "Subject line",
    "preview text": "Preview text",
    "email objective": "Objective",
    "email body summary": "Summary",
    "email body": "Email body",
    "headline": "Headline",
    "primary text": "Primary text",
    "cta": "CTA",
    "target keyword": "Target keyword",
    "outline": "Outline",
    "objective": "Objective",
    "suggested visual": "Suggested visual",
}


def _render_full_content(asset: dict[str, str]) -> None:
    full_content = asset.get("full_content") or asset.get("preview") or ""
    fields = _parse_content_fields(full_content)
    theme = _extract_post_theme(full_content)

    if theme and asset.get("content_type") == "Social Post":
        st.markdown(f"**Theme:** {theme}")

    if fields:
        visible = [(k, v) for k, v in fields.items() if v.strip()]
        for index, (key, value) in enumerate(visible):
            label = _FIELD_LABELS.get(key, key.replace("_", " ").title())
            st.markdown(f"**{label}**")
            st.markdown(value)
            if index < len(visible) - 1:
                st.divider()
    elif full_content:
        st.markdown(full_content)

    persona = asset.get("target_persona") or ""
    pillar = asset.get("message_pillar") or ""
    objective = asset.get("objective") or ""
    notes = asset.get("notes") or ""
    cta = asset.get("cta") or ""

    if persona and "target persona" not in fields:
        st.markdown(f"**Target persona:** {persona}")
    if pillar and "message angle" not in fields:
        st.markdown(f"**Message pillar:** {pillar or 'Not specified'}")
    if objective and "objective" not in fields and "email objective" not in fields:
        st.markdown(f"**Objective:** {objective or 'Not specified'}")
    if cta and "cta" not in fields:
        st.markdown(f"**CTA:** {_strip_markdown(cta)}")
    if notes and "brand alignment note" not in fields:
        st.markdown(f"**Notes:** {notes}")


def render_content_card(asset: dict[str, str], *, key_suffix: str = "") -> None:
    title = html.escape(asset.get("title") or "Content")
    content_type = html.escape(asset.get("content_type") or "Other")
    channel = html.escape(asset.get("channel") or "Other")
    funnel = html.escape(asset.get("funnel_stage") or "Unknown")
    cta = asset.get("cta") or ""
    status = asset.get("status") or ""
    type_cls = _tag_class(asset.get("content_type", "Other"))
    preview_html = _build_card_preview_html(asset)

    status_html = ""
    if status:
        status_html = f'<span class="content-tag-muted">{html.escape(status)}</span>'

    cta_html = ""
    if cta:
        cta_clean = _strip_markdown(cta).strip('"')
        cta_html = (
            '<div class="content-card-divider"></div>'
            f'<p class="content-card-meta">'
            f'<span class="content-card-meta-label">CTA</span> '
            f"{html.escape(cta_clean)}</p>"
        )

    st.markdown(
        f'<div class="content-review-card content-gallery-card">'
        f'<div class="content-review-header">'
        f'<div class="content-review-title">{title}</div>'
        f'<div class="content-tags">'
        f'<span class="{type_cls}">{content_type}</span>'
        f'<span class="content-tag-muted">{channel}</span>'
        f'<span class="content-tag-muted">{funnel}</span>'
        f'{status_html}'
        f"</div></div>"
        f'<div class="content-card-body">{preview_html}{cta_html}</div>'
        f"</div>",
        unsafe_allow_html=True,
    )

    with st.expander("View full content", expanded=False):
        _render_full_content(asset)


def _filter_assets(
    assets: list[dict[str, str]],
    types: list[str],
    channels: list[str],
    stages: list[str],
) -> list[dict[str, str]]:
    filtered = assets
    if types:
        filtered = [a for a in filtered if a.get("content_type") in types]
    if channels:
        filtered = [a for a in filtered if a.get("channel") in channels]
    if stages:
        filtered = [a for a in filtered if a.get("funnel_stage") in stages]
    return filtered


def render_content_gallery(assets: list[dict[str, str]], *, key_prefix: str = "main", columns_count: int = 3) -> None:
    if not assets:
        st.caption("No content assets match the current filters.")
        return

    for row_start in range(0, len(assets), columns_count):
        row = assets[row_start : row_start + columns_count]
        st.markdown('<div class="content-gallery-row-marker"></div>', unsafe_allow_html=True)
        cols = st.columns(columns_count, gap="large")
        for col_index, col in enumerate(cols):
            with col:
                if col_index < len(row):
                    render_content_card(
                        row[col_index],
                        key_suffix=f"{key_prefix}_{row_start}_{col_index}",
                    )


def _render_filters(assets: list[dict[str, str]]) -> tuple[list[str], list[str], list[str]]:
    available_types = sorted({a["content_type"] for a in assets if a.get("content_type")})
    available_channels = sorted({a["channel"] for a in assets if a.get("channel")})
    available_stages = sorted({a["funnel_stage"] for a in assets if a.get("funnel_stage")})

    if not (available_types or available_channels or available_stages):
        return [], [], []

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
            key="content_filter_type",
        )
    with c2:
        channel_filter = st.multiselect(
            "Channel",
            options=[c for c in CHANNELS if c in available_channels],
            default=[],
            key="content_filter_channel",
        )
    with c3:
        stage_filter = st.multiselect(
            "Funnel Stage",
            options=[s for s in FUNNEL_STAGES if s in available_stages],
            default=[],
            key="content_filter_stage",
        )
    return type_filter, channel_filter, stage_filter


def _section_summary_body(sections: list[dict[str, Any]]) -> str:
    for section in reversed(sections):
        if not isinstance(section, dict):
            continue
        if "content strategy summary" in _normalize_title(section.get("title") or ""):
            return (section.get("body") or "").strip()
    return ""


def _is_structured_gallery(assets: list[dict[str, str]]) -> bool:
    if len(assets) >= 2:
        return True
    if len(assets) == 1:
        return assets[0].get("content_type") != "Other"
    return False


def render_content_page(content_ui: dict[str, Any]) -> None:
    """Render the full Content Agent gallery page from UI JSON."""
    sections = content_ui.get("sections") or []
    assets = normalize_content_assets(content_ui)
    structured = _is_structured_gallery(assets)

    status = content_ui.get("status", "completed")
    badge = "● Content Complete" if status == "completed" else f"● Content {status.title()}"
    metrics = derive_content_gallery_metrics(assets, content_ui)
    render_hero(
        CONTENT_HERO_TITLE,
        CONTENT_HERO_SUBTITLE,
        badge,
        metrics,
        metric_labels=CONTENT_METRIC_LABELS,
    )

    summary = _section_summary_body(sections)
    if summary:
        preview = summary[:1500] + ("…" if len(summary) > 1500 else "")
        render_executive_summary("Content Strategy Summary", preview)

    st.markdown('<div class="content-panel">', unsafe_allow_html=True)

    if not structured:
        st.info("Structured content assets were not found. Displaying the available Content Agent output.")
        for section in sections:
            if not isinstance(section, dict):
                continue
            norm = _normalize_title(section.get("title") or "")
            if norm in {"content priorities and handoff notes"}:
                continue
            body = (section.get("body") or "").strip()
            if not body:
                continue
            with st.expander(_clean_title(section.get("title") or "Section"), expanded=False):
                st.markdown(body)
        st.markdown("</div>", unsafe_allow_html=True)
        with st.expander("Raw Content JSON"):
            st.json(content_ui)
        return

    render_content_calendar_table(extract_calendar_table_rows(content_ui))

    type_filter, channel_filter, stage_filter = _render_filters(assets)
    filtered = _filter_assets(assets, type_filter, channel_filter, stage_filter)

    gallery_items = gallery_assets_only(filtered)

    st.markdown(
        '<div class="content-gallery-shell">'
        '<div class="content-gallery-shell-header">'
        '<div class="section-card-header">Content Gallery</div>'
        '<p class="content-gallery-caption">Scan, compare, and review market-ready content assets.</p>'
        "</div></div>",
        unsafe_allow_html=True,
    )
    render_content_gallery(gallery_items, key_prefix="gallery")
    st.markdown('<div class="content-gallery-shell-footer"></div>', unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

    with st.expander("Raw Content JSON"):
        st.json(content_ui)
