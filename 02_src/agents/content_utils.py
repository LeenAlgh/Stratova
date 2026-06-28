"""Flatten Content Agent JSON into reviewable items with tags."""

from __future__ import annotations

TYPE_LABELS = {
    "calendar": "Calendar",
    "seo": "SEO",
    "social": "Social",
    "blog": "Blog",
    "email": "Email",
    "ad": "Ad",
}

PLATFORM_LABELS = {
    "linkedin": "LinkedIn",
    "x": "X",
    "instagram": "Instagram",
}

FLAT_CONTENT_KEYS = (
    "content_calendar",
    "seo_keywords",
    "social_posts",
    "blog_posts",
    "blog_plan",
    "email_campaign",
    "ad_copy",
)


def normalize_content_payload(content_data: dict) -> dict:
    """
    Unwrap ORCA nested content agent output into a flat dict for flatten_content_items.
    Prefers blog_posts (full articles) over blog_plan (outlines only).
    """
    if not isinstance(content_data, dict):
        return {}

    merged: dict = {}

    if any(content_data.get(key) for key in FLAT_CONTENT_KEYS):
        merged.update({k: content_data[k] for k in FLAT_CONTENT_KEYS if content_data.get(k) is not None})

    output = content_data.get("output")
    if isinstance(output, dict):
        for key in FLAT_CONTENT_KEYS:
            if output.get(key) is not None and key not in merged:
                merged[key] = output[key]
        components = output.get("components")
        if isinstance(components, dict):
            for key in FLAT_CONTENT_KEYS:
                if components.get(key) is not None and key not in merged:
                    merged[key] = components[key]

    if merged.get("blog_posts") and merged.get("blog_plan"):
        merged.pop("blog_plan", None)

    return merged


def _snippet(text: str, max_len: int = 220) -> str:
    cleaned = " ".join(str(text).split())
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 1] + "…"


def flatten_content_items(content: dict) -> list[dict]:
    content = normalize_content_payload(content)
    items: list[dict] = []

    calendar = content.get("content_calendar")
    if calendar:
        items.append({
            "id": "content_calendar",
            "type": "calendar",
            "type_label": TYPE_LABELS["calendar"],
            "platform": None,
            "title": "Content Calendar",
            "body": str(calendar),
            "snippet": _snippet(calendar),
            "tags": ["Calendar"],
        })

    seo = content.get("seo_keywords")
    if isinstance(seo, dict):
        if "primary" in seo:
            items.append({
                "id": "seo_keywords",
                "type": "seo",
                "type_label": TYPE_LABELS["seo"],
                "platform": None,
                "title": "SEO Keywords",
                "body": str(seo),
                "snippet": _snippet(", ".join(seo.get("primary", []))),
                "tags": ["SEO"],
            })
        else:
            for topic, keywords in seo.items():
                items.append({
                    "id": f"seo_keywords:{topic}",
                    "type": "seo",
                    "type_label": TYPE_LABELS["seo"],
                    "platform": None,
                    "title": topic,
                    "body": str(keywords),
                    "snippet": _snippet(keywords),
                    "tags": ["SEO"],
                })
    elif seo:
        items.append({
            "id": "seo_keywords",
            "type": "seo",
            "type_label": TYPE_LABELS["seo"],
            "platform": None,
            "title": "SEO Keywords",
            "body": str(seo),
            "snippet": _snippet(seo),
            "tags": ["SEO"],
        })

    social = content.get("social_posts")
    if isinstance(social, dict):
        for platform, posts in social.items():
            label = PLATFORM_LABELS.get(platform.lower(), platform.title())
            if isinstance(posts, list):
                for idx, post in enumerate(posts, 1):
                    if isinstance(post, dict):
                        title = post.get("theme") or post.get("hook") or f"{label} Post {idx}"
                        body = post.get("body") or str(post)
                    else:
                        title = f"{label} Post {idx}"
                        body = str(post)
                    items.append({
                        "id": f"social_posts:{platform}:{idx}",
                        "type": "social",
                        "type_label": TYPE_LABELS["social"],
                        "platform": label,
                        "title": title,
                        "body": body,
                        "snippet": _snippet(body),
                        "tags": ["Social", label],
                    })
            else:
                items.append({
                    "id": f"social_posts:{platform}",
                    "type": "social",
                    "type_label": TYPE_LABELS["social"],
                    "platform": label,
                    "title": f"{label} Posts",
                    "body": str(posts),
                    "snippet": _snippet(posts),
                    "tags": ["Social", label],
                })
    elif social:
        items.append({
            "id": "social_posts",
            "type": "social",
            "type_label": TYPE_LABELS["social"],
            "platform": None,
            "title": "Social Posts",
            "body": str(social),
            "snippet": _snippet(social),
            "tags": ["Social"],
        })

    blogs = content.get("blog_posts")
    if isinstance(blogs, dict):
        for title, body in blogs.items():
            items.append({
                "id": f"blog_posts:{title}",
                "type": "blog",
                "type_label": TYPE_LABELS["blog"],
                "platform": "Blog",
                "title": title,
                "body": str(body),
                "snippet": _snippet(body),
                "tags": ["Blog"],
            })
    elif blogs:
        items.append({
            "id": "blog_posts",
            "type": "blog",
            "type_label": TYPE_LABELS["blog"],
            "platform": "Blog",
            "title": "Blog Posts",
            "body": str(blogs),
            "snippet": _snippet(blogs),
            "tags": ["Blog"],
        })

    email = content.get("email_campaign")
    if email:
        items.append({
            "id": "email_campaign",
            "type": "email",
            "type_label": TYPE_LABELS["email"],
            "platform": "Email",
            "title": "Email Campaign",
            "body": str(email),
            "snippet": _snippet(email),
            "tags": ["Email"],
        })

    ads = content.get("ad_copy")
    if ads:
        items.append({
            "id": "ad_copy",
            "type": "ad",
            "type_label": TYPE_LABELS["ad"],
            "platform": "Ads",
            "title": "Ad Copy",
            "body": str(ads),
            "snippet": _snippet(ads),
            "tags": ["Ad"],
        })

    return items
