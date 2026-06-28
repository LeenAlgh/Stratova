"""Parse content calendar and blog plan into executable blog/article topics."""

from __future__ import annotations

import json
import re

BLOG_CONTENT_TYPES = frozenset({
    "blog article",
    "article",
    "case study",
    "whitepaper",
    "blog post",
    "blog",
})


def _normalize_title(title: str) -> str:
    return " ".join(title.strip().split()).lower()


def _parse_markdown_table_rows(text: str) -> list[dict[str, str]]:
    """Parse markdown pipe tables into row dicts keyed by normalized header names."""
    rows: list[dict[str, str]] = []
    headers: list[str] = []

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if not cells:
            continue
        if all(re.match(r"^[-:]+$", cell.replace(" ", "")) for cell in cells):
            continue
        if not headers:
            headers = [_normalize_header(cell) for cell in cells]
            continue
        if len(cells) < len(headers):
            cells.extend([""] * (len(headers) - len(cells)))
        rows.append(dict(zip(headers, cells[: len(headers)])))

    return rows


def _normalize_header(header: str) -> str:
    key = header.strip().lower()
    aliases = {
        "content type": "content_type",
        "type": "content_type",
        "posting date": "day",
        "day": "day",
        "platform": "platform",
        "topic": "topic",
        "title": "topic",
        "objective": "objective",
        "target persona": "persona",
        "persona": "persona",
    }
    return aliases.get(key, key.replace(" ", "_"))


def _is_blog_content_type(content_type: str) -> bool:
    normalized = content_type.strip().lower()
    if normalized in BLOG_CONTENT_TYPES:
        return True
    return any(keyword in normalized for keyword in ("blog", "article", "case study", "whitepaper"))


def _topic_from_row(row: dict[str, str]) -> str:
    for key in ("topic", "title", "objective"):
        value = row.get(key, "").strip()
        if value:
            return value
    return ""


def _parse_calendar_topics(content_calendar: str) -> list[dict]:
    topics: list[dict] = []
    seen: set[str] = set()

    for row in _parse_markdown_table_rows(content_calendar):
        content_type = row.get("content_type", "")
        if not _is_blog_content_type(content_type):
            continue
        title = _topic_from_row(row)
        if not title:
            continue
        key = _normalize_title(title)
        if key in seen:
            continue
        seen.add(key)
        topics.append({
            "title": title,
            "source": "calendar",
            "day": row.get("day") or None,
            "persona": row.get("persona") or None,
            "outline": "",
        })

    # Fallback: bullet/list lines mentioning blog/article types without a table
    if not topics:
        pattern = re.compile(
            r"(?:blog\s+article|article|case\s+study|whitepaper)[:\s\-|]+(.+?)(?:\.|$)",
            re.IGNORECASE,
        )
        for match in pattern.finditer(content_calendar):
            title = match.group(1).strip(" |-*")
            if len(title) < 10:
                continue
            key = _normalize_title(title)
            if key in seen:
                continue
            seen.add(key)
            topics.append({
                "title": title,
                "source": "calendar",
                "day": None,
                "persona": None,
                "outline": "",
            })

    return topics


def _parse_blog_plan_topics(blog_plan: str) -> list[dict]:
    topics: list[dict] = []
    seen: set[str] = set()

    patterns = [
        re.compile(r"^\s*\d+[\.\)]\s*(?:\*\*)?(.+?)(?:\*\*)?\s*$", re.MULTILINE),
        re.compile(r"^\s*[-*]\s*\*\*(?:Blog\s+)?Topic\*\*[:\s]+(.+?)\s*$", re.IGNORECASE | re.MULTILINE),
        re.compile(r"^\s*###\s*(?:Blog\s+)?\d*[:\s]+(.+?)\s*$", re.IGNORECASE | re.MULTILINE),
        re.compile(r"^\s*\*\*Topic\*\*[:\s]+(.+?)\s*$", re.IGNORECASE | re.MULTILINE),
    ]

    for pattern in patterns:
        for match in pattern.finditer(blog_plan):
            raw = match.group(1).strip()
            title = re.split(r"\s*[-–—]\s*(?:Target|Keyword|Persona|Funnel|Outline)", raw, maxsplit=1)[0]
            title = title.strip(" *#")
            if len(title) < 8:
                continue
            key = _normalize_title(title)
            if key in seen:
                continue
            seen.add(key)
            topics.append({
                "title": title,
                "source": "blog_plan",
                "day": None,
                "persona": None,
                "outline": _extract_outline_for_topic(blog_plan, title),
            })

    return topics


def _extract_outline_for_topic(blog_plan: str, title: str) -> str:
    """Best-effort extraction of outline text following a topic heading."""
    escaped = re.escape(title[:40])
    match = re.search(
        rf"{escaped}.*?(?:Outline|outline)[:\s]+(.+?)(?:\n\n|\n#|\n\*\*|\Z)",
        blog_plan,
        re.DOTALL | re.IGNORECASE,
    )
    if match:
        return match.group(1).strip()
    return ""


def extract_blog_topics(content_calendar: str, blog_plan: str) -> list[dict]:
    """
    Merge and dedupe blog/article topics from calendar and blog plan.
    Calendar topics take precedence; blog_plan fills gaps.
    """
    merged: list[dict] = []
    seen: set[str] = set()

    for topic in _parse_calendar_topics(content_calendar):
        key = _normalize_title(topic["title"])
        seen.add(key)
        merged.append(topic)

    for topic in _parse_blog_plan_topics(blog_plan):
        key = _normalize_title(topic["title"])
        if key in seen:
            continue
        seen.add(key)
        merged.append(topic)

    return merged


def extract_blog_topics_with_llm_fallback(
    content_calendar: str,
    blog_plan: str,
    llm_extract_fn,
) -> list[dict]:
    """Parse topics; if none found, use a single LLM extraction call."""
    topics = extract_blog_topics(content_calendar, blog_plan)
    if topics:
        return topics

    combined = f"Content Calendar:\n{content_calendar}\n\nBlog Plan:\n{blog_plan}"
    prompt = """
Extract every blog article, case study, and whitepaper topic from the content calendar and blog plan.

Return ONLY valid JSON — an array of objects:
[
  {"title": "...", "source": "calendar|blog_plan", "day": null or "Day 5", "persona": null or "...", "outline": ""}
]

Include only long-form written content (blogs, articles, case studies, whitepapers). Skip social posts and emails.
"""
    try:
        raw = llm_extract_fn(combined, prompt)
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        parsed = json.loads(cleaned)
        if isinstance(parsed, list):
            return [
                {
                    "title": str(item.get("title", "")).strip(),
                    "source": item.get("source", "calendar"),
                    "day": item.get("day"),
                    "persona": item.get("persona"),
                    "outline": item.get("outline", ""),
                }
                for item in parsed
                if str(item.get("title", "")).strip()
            ]
    except Exception:
        pass

    return []
