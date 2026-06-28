"""Content Agent read-only view for the Dashboard."""

import os

import httpx
import streamlit as st

from ui.api_client import StratovaAPI
from ui.components.hero import render_hero
from ui.components.report_sections import render_report_sections
from ui.report_parser import parse_report_txt
from ui.run_loader import load_agent_ui
from ui.utils.content_gallery import (
    CONTENT_HERO_SUBTITLE,
    CONTENT_HERO_TITLE,
    CONTENT_METRIC_LABELS,
    render_content_page,
)
from ui.utils.markdown import extract_first_heading, extract_first_paragraph
from ui.utils.metrics import derive_content_metrics

EMPTY_METRICS = {
    "blog_posts": "—",
    "social_posts": "—",
    "calendar_duration": "—",
    "total_content": "—",
}


def _load_content(api: StratovaAPI, company: str) -> tuple[dict | None, str | None]:
    try:
        return api.get_content_json(company), None
    except httpx.HTTPError:
        pass
    try:
        text_payload = api.get_content_text(company)
        return None, text_payload.get("content")
    except httpx.HTTPError as exc:
        return None, str(exc)
    return None, None


def _render_social_posts(social: dict | str) -> None:
    if isinstance(social, str):
        st.markdown(social)
        return

    for platform, posts in social.items():
        with st.expander(f"{platform.title()} Posts", expanded=False):
            if isinstance(posts, list):
                for i, post in enumerate(posts, 1):
                    if isinstance(post, dict):
                        st.markdown(f"**{post.get('theme', f'Post {i}')}**")
                        if post.get("hook"):
                            st.markdown(f"*{post['hook']}*")
                        st.markdown(post.get("body", ""))
                        if post.get("hashtags"):
                            st.caption(" ".join(post["hashtags"]))
                        if post.get("cta"):
                            st.caption(f"CTA: {post['cta']}")
                    else:
                        st.markdown(str(post))
            else:
                st.markdown(str(posts))


def _render_blog_posts(blogs: dict | str) -> None:
    if isinstance(blogs, str):
        st.markdown(blogs)
        return
    for title, body in blogs.items():
        with st.expander(title, expanded=False):
            st.markdown(body if isinstance(body, str) else str(body))


def _render_images(api: StratovaAPI, data: dict, company: str) -> None:
    images = data.get("images") or []
    if not images:
        return

    st.markdown(
        '<div class="section-card"><div class="section-card-header">🖼 Generated Images</div></div>',
        unsafe_allow_html=True,
    )
    cols = st.columns(min(len(images), 3))
    slug = company.lower().replace(" ", "_")
    for idx, img in enumerate(images):
        path = img if isinstance(img, str) else img.get("path", "")
        if not path:
            continue
        filename = os.path.basename(path)
        url = f"{api.base_url}/content/images/{slug}/images/{filename}"
        with cols[idx % len(cols)]:
            st.image(url, caption=filename, use_container_width=True)


def render(api: StratovaAPI, company: str, client_config: dict, reports: dict) -> None:
    ui_data = load_agent_ui("content")
    if ui_data:
        render_content_page(ui_data)
        return

    data, text_fallback = _load_content(api, company)
    if not data and not text_fallback:
        render_hero(
            CONTENT_HERO_TITLE,
            CONTENT_HERO_SUBTITLE,
            "● Not started",
            EMPTY_METRICS,
            metric_labels=CONTENT_METRIC_LABELS,
        )
        st.info("No content output in the latest run. Start a **New Run** to generate results.")
        return

    if data:
        calendar = data.get("content_calendar") or ""
        title = extract_first_heading(calendar, f"Content Plan — {company}")
        subtitle = extract_first_paragraph(calendar, max_len=100) or "Social, blog, email & ad copy"
        metrics = derive_content_metrics(data)
        legacy_metrics = {
            "blog_posts": metrics.get("data_points", "—"),
            "social_posts": metrics.get("sources", "—"),
            "calendar_duration": "—",
            "total_content": metrics.get("data_points", "—"),
        }
        render_hero(title, subtitle, "● Content Complete", legacy_metrics, metric_labels=CONTENT_METRIC_LABELS)

        st.markdown('<div class="content-panel">', unsafe_allow_html=True)

        seo = data.get("seo_keywords")
        if seo:
            with st.expander("SEO Keywords", expanded=False):
                if isinstance(seo, dict) and "primary" in seo:
                    st.json(seo)
                else:
                    st.markdown(str(seo))

        social = data.get("social_posts")
        if social:
            st.markdown(
                '<div class="section-card"><div class="section-card-header">📱 Social Posts</div></div>',
                unsafe_allow_html=True,
            )
            _render_social_posts(social)

        blogs = data.get("blog_posts")
        if blogs:
            st.markdown(
                '<div class="section-card"><div class="section-card-header">📝 Blog Posts</div></div>',
                unsafe_allow_html=True,
            )
            _render_blog_posts(blogs)

        email = data.get("email_campaign")
        if email:
            with st.expander("Email Campaign", expanded=False):
                st.markdown(email if isinstance(email, str) else str(email))

        ads = data.get("ad_copy")
        if ads:
            with st.expander("Ad Copy", expanded=False):
                st.markdown(ads if isinstance(ads, str) else str(ads))

        _render_images(api, data, company)
        st.markdown("</div>", unsafe_allow_html=True)
    elif text_fallback:
        report = parse_report_txt(text_fallback)
        render_hero(
            report.title,
            "Social, blog, email & ad copy",
            "● Content Complete",
            EMPTY_METRICS,
            metric_labels=CONTENT_METRIC_LABELS,
        )
        render_report_sections(report)
