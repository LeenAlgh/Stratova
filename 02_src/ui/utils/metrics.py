"""Derive hero metrics from agent JSON output."""

from __future__ import annotations

import re
from typing import Any


def _count_nonempty_strings(data: dict, keys: list[str]) -> int:
    return sum(1 for key in keys if data.get(key) and str(data[key]).strip())


_ICP_COMPONENT_TITLES = frozenset({
    "firmographics",
    "pain points",
    "buying triggers",
    "decision criteria",
    "disqualifiers",
})


def _count_icp_from_sections(sections: list[dict]) -> int:
    personas = sum(
        1 for s in sections
        if re.search(r"persona\s*\d", s.get("title") or "", re.IGNORECASE)
    )
    if personas:
        return personas
    icp_parts = sum(
        1 for s in sections
        if (s.get("title") or "").strip().lower() in _ICP_COMPONENT_TITLES
    )
    return icp_parts or 0


def _count_recommended_channels_from_sections(sections: list[dict]) -> int:
    for section in sections:
        if "recommended channel" not in (section.get("title") or "").lower():
            continue
        body = section.get("body") or ""
        numbered = re.findall(r"^\d+\.\s+\*\*", body, re.MULTILINE)
        if numbered:
            return len(numbered)
        bullets = re.findall(r"^[-*]\s+\*\*", body, re.MULTILINE)
        return len(bullets) if bullets else 0
    return 0


def _count_recommended_channels_from_text(text: str) -> int:
    if not text:
        return 0
    numbered = re.findall(r"^\d+\.\s+\*\*", text, re.MULTILINE)
    if numbered:
        return len(numbered)
    bullets = re.findall(r"^[-*]\s+\*\*", text, re.MULTILINE)
    return len(bullets) if bullets else 0


def _strategy_timeline_from_sections(sections: list[dict]) -> str:
    months: list[int] = []
    for section in sections:
        match = re.match(r"month\s*(\d+)", section.get("title") or "", re.IGNORECASE)
        if match:
            months.append(int(match.group(1)))
    if months:
        span = max(months)
        return f"{span} mo" if span == 1 else f"{span} mos"
    return "—"


def _strategy_timeline_from_text(*texts: str) -> str:
    months: list[int] = []
    for text in texts:
        if not text:
            continue
        months.extend(int(m.group(1)) for m in re.finditer(r"month\s*(\d+)", text, re.IGNORECASE))
    if months:
        span = max(months)
        return f"{span} mo" if span == 1 else f"{span} mos"
    return "—"


def _count_personas_from_text(text: str) -> int:
    if not text:
        return 0
    personas = re.findall(r"persona\s*\d+", text, re.IGNORECASE)
    return len(personas) if personas else (1 if text.strip() else 0)


STRATEGY_METRIC_LABELS = {
    "icp_count": "ICP",
    "channels": "CHANNELS",
    "time_to_market": "TIME TO MARKET",
}


def derive_strategy_ui_metrics(ui_payload: dict[str, Any]) -> dict[str, str]:
    sections = ui_payload.get("sections") or []
    icp_count = _count_icp_from_sections(sections)
    channels = _count_recommended_channels_from_sections(sections)
    timeline = _strategy_timeline_from_sections(sections)
    return {
        "icp_count": str(icp_count) if icp_count else "—",
        "channels": str(channels) if channels else "—",
        "time_to_market": timeline,
    }


def derive_research_metrics(data: dict) -> dict[str, str]:
    ck = data.get("company_knowledge") or {}
    sources = ck.get("sources") or []
    sections = ck.get("sections") or {}
    source_count = len(sources)
    data_points = (
        _count_nonempty_strings(
            data,
            [
                "market_scope",
                "market_research",
                "competitor_analysis",
                "research_summary",
                "marketing_channels",
            ],
        )
        + len(sections)
    )
    confidence = "94%" if source_count >= 3 else "78%" if source_count >= 1 else "—"
    return {
        "sources": str(source_count),
        "data_points": str(data_points),
        "confidence": confidence,
        "processing_time": "—",
    }


def derive_strategy_metrics(data: dict) -> dict[str, str]:
    personas_text = data.get("personas") or ""
    channels_text = data.get("recommended_channels") or ""
    gtm_text = data.get("gtm_strategy") or ""
    icp_text = data.get("icp") or ""

    icp_count = _count_personas_from_text(personas_text)
    if icp_count <= 1 and icp_text.strip():
        icp_count = max(icp_count, 1)

    channels = len(data.get("content_strategy", {}).get("channel_plan") or [])
    if not channels:
        channels = _count_recommended_channels_from_text(channels_text)

    return {
        "icp_count": str(icp_count) if icp_count else "—",
        "channels": str(channels) if channels else "—",
        "time_to_market": _strategy_timeline_from_text(gtm_text),
    }


def derive_content_metrics(data: dict) -> dict[str, str]:
    social = data.get("social_posts")
    blogs = data.get("blog_posts")
    social_count = 0
    if isinstance(social, dict):
        for posts in social.values():
            if isinstance(posts, list):
                social_count += len(posts)
    blog_count = len(blogs) if isinstance(blogs, dict) else 0
    data_points = social_count + blog_count + (1 if data.get("email_campaign") else 0) + (1 if data.get("ad_copy") else 0)
    return {
        "sources": str(social_count),
        "data_points": str(data_points),
        "confidence": "90%" if data_points else "—",
        "processing_time": "—",
    }


def derive_metrics(agent_id: str, data: dict[str, Any]) -> dict[str, str]:
    if agent_id == "research":
        return derive_research_metrics(data)
    if agent_id == "strategy":
        return derive_strategy_metrics(data)
    if agent_id == "content":
        return derive_content_metrics(data)
    return {"sources": "—", "data_points": "—", "confidence": "—", "processing_time": "—"}


def derive_ui_json_metrics(agent_id: str, ui_payload: dict[str, Any]) -> dict[str, str]:
    """Derive hero metrics from orchestration UI JSON (sections, guardrails, metrics)."""
    sections = ui_payload.get("sections") or []
    metrics = ui_payload.get("metrics") or {}
    guardrails = ui_payload.get("guardrails") or {}

    confidence = "—"
    if guardrails.get("score") is not None:
        confidence = f"{guardrails['score']}%"

    if agent_id == "research":
        source_keywords = ("competitor", "channel", "market", "audience")
        sources = sum(
            1 for s in sections
            if any(kw in (s.get("title") or "").lower() for kw in source_keywords)
        )
        return {
            "sources": str(sources or len(sections)),
            "data_points": str(len(sections)),
            "confidence": confidence,
            "processing_time": "—",
        }

    if agent_id == "brand":
        overall = metrics.get("overall_score")
        return {
            "sources": str(metrics.get("high_count", "—")),
            "data_points": str(metrics.get("total_items", "—")),
            "confidence": f"{overall}%" if overall is not None else confidence,
            "processing_time": "—",
        }

    if agent_id == "strategy":
        return derive_strategy_ui_metrics(ui_payload)

    if agent_id == "content":
        platform_count = sum(
            1 for s in sections
            if re.match(r"^\d+\.\s*(linkedin|twitter|facebook)", s.get("title") or "", re.IGNORECASE)
        )
        blog_count = sum(
            1 for s in sections
            if "blog topic" in (s.get("title") or "").lower()
        )
        calendar_count = sum(
            1 for s in sections
            if "calendar" in (s.get("title") or "").lower()
        )
        data_points = blog_count + platform_count + (1 if calendar_count else 0)
        score = guardrails.get("score")
        return {
            "sources": str(platform_count) if platform_count else "—",
            "data_points": str(data_points) if data_points else str(len(sections)),
            "confidence": f"{score}%" if score is not None else confidence,
            "processing_time": "—",
        }

    return {
        "sources": str(len(sections)),
        "data_points": str(len(sections)),
        "confidence": confidence,
        "processing_time": "—",
    }
