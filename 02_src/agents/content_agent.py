"""
Content Agent — Ready-to-Copy Content Generation.

Designed for ORCA/LangGraph:
- Receives Strategy Agent output from LangGraph state.
- Keeps a content calendar.
- Generates ready-to-copy content assets from the strategy and calendar.
- Does NOT save files.
- Does NOT read local files.
- Does NOT create strategy.
- Does NOT perform market research.
- ORCA handles saving UI JSON / TXT / MD outputs.
"""

import json
import os
import sys
import re
from datetime import datetime
from typing import Any

from langchain.tools import tool
from langchain.agents import create_agent

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from knowledge_base.rag import ask_with_context, retrieve_context_formatted, llm


# =========================
# System Prompt
# =========================

CONTENT_SYSTEM = """You are an expert B2B Content Generation Agent.

You work AFTER the Strategy Agent in an ORCA/LangGraph workflow.

Your role is to turn the approved GTM strategy into ready-to-copy marketing content assets.

You receive:
- Strategy Agent output
- Brand/company context
- Optional long-term memory context

You do NOT:
- create a new GTM strategy
- perform new market research
- create content plans only
- write instructions for content
- write directions
- write summaries instead of usable content
- save files
- read local files
- rebuild the knowledge base
- review brand alignment

You DO:
- create a content calendar
- generate ready-to-copy social posts
- generate ready-to-copy email bodies
- generate ready-to-copy paid ad copy
- generate ready-to-copy blog/article drafts
- generate ready-to-copy sales enablement copy

Important rules:
- Use the Strategy Agent output as the source of truth.
- Follow the approved ICP, personas, positioning, messaging pillars, and channels.
- Use brand/company context only for tone and alignment.
- Use memory only as supporting context, not as the source of truth.
- Do not invent new positioning.
- Do not contradict the strategy.
- Do not create unsupported claims.
- Avoid hype, exaggerated AI claims, and absolutist language.
- Keep the tone B2B, credible, specific, and enterprise-focused.
- Write content that a marketing team can copy, review, and publish.
- If information is missing, make minimal reasonable assumptions and state them briefly.

The calendar is allowed because it is the publishing schedule.
But all other content outputs must be ready-to-copy assets, not plans or instructions.

Final output must include:
1. Content Calendar
2. Social Media Posts
3. Email Sequence
4. Paid Ad Copy
5. Blog Articles
6. Sales Enablement Copy
"""


# =========================
# Safety / Cleanup
# =========================

CONTENT_HYPE_REPLACEMENTS = [
    (re.compile(r"Join the AI Revolution", re.IGNORECASE), "Start your AI adoption journey"),
    (re.compile(r"\bAI Revolution\b", re.IGNORECASE), "AI adoption"),
    (re.compile(r"\brevolutionize everything\b", re.IGNORECASE), "improve workflows thoughtfully"),
    (re.compile(r"\bguaranteed\s+accuracy\b", re.IGNORECASE), "reliable outcomes"),
    (re.compile(r"\b100%\s+accuracy\b", re.IGNORECASE), "strong accuracy"),
    (re.compile(r"\binstant(?:ly)?\s+transform", re.IGNORECASE), "support practical transformation"),
]


def sanitize_content_language(text: str) -> str:
    """
    Replace hype phrases with enterprise-credible alternatives.
    """

    if not text:
        return text

    cleaned = text

    for pattern, replacement in CONTENT_HYPE_REPLACEMENTS:
        cleaned = pattern.sub(replacement, cleaned)

    return cleaned


# =========================
# Context Helpers
# =========================

def format_strategy_for_content(strategy_data: dict | str) -> str:
    """
    Convert Strategy Agent output and brand guidance into a clean content context.
    """

    if isinstance(strategy_data, str):
        return strategy_data

    output = strategy_data.get("output", strategy_data)

    strategy_output = output.get("strategy_output", "")
    brand_guidance = output.get("brand_guidance", {})

    # Fallback if strategy output is nested differently
    if not strategy_output:
        possible_keys = [
            "gtm_strategy",
            "strategy",
            "positioning",
            "messaging_pillars",
            "icp",
            "personas",
            "recommended_channels",
            "channels",
        ]

        parts = []

        for key in possible_keys:
            if output.get(key):
                parts.append(f"## {key}\n{output.get(key)}")

        strategy_output = "\n\n".join(parts) if parts else json.dumps(
            output,
            indent=2,
            ensure_ascii=False,
        )

    return f"""
Strategy Output:
{strategy_output}

Brand Guidance:
{json.dumps(brand_guidance, indent=2, ensure_ascii=False)}
"""


def get_brand_context() -> str:
    """
    Retrieve brand/company context from the knowledge base.
    This is RAG read-only. It does not rebuild Chroma.
    """

    try:
        return retrieve_context_formatted(
            "brand voice tone messaging guidelines company values positioning vocabulary"
        )
    except Exception as e:
        return f"Brand context unavailable: {str(e)}"


def generate_content(context: str, task_prompt: str) -> str:
    """
    Generate content grounded in strategy and brand/company context.
    """

    brand_context = get_brand_context()

    combined_context = f"""
## Strategy Context
{context}

## Brand / Company Context
{brand_context}
"""

    result = ask_with_context(
        combined_context,
        task_prompt,
        system=CONTENT_SYSTEM,
    )

    return sanitize_content_language(str(result))


# =========================
# Content Tools
# =========================

@tool
def generate_content_calendar(strategy_context: str) -> str:
    """
    Generate a content calendar from the Strategy Agent output.
    """

    prompt = """
Create a 30-day content calendar from the strategy context.

The calendar is a publishing schedule, not a content plan.

For each content item include:
- Day
- Platform
- Content type
- Asset title
- Topic
- Target persona
- Funnel stage
- Objective
- CTA
- Brand alignment note

Rules:
- Each item should be specific enough to generate a real content asset from it.
- Do not write generic instructions.
- Do not create a new strategy.
- Do not invent new positioning.
- Use the Strategy Agent output as the source of truth.
- Use practical, enterprise-credible language.
"""

    return generate_content(strategy_context, prompt)


@tool
def generate_seo_keywords(strategy_context: str, content_calendar: str) -> str:
    """
    Generate SEO keywords to support the generated content assets.
    """

    prompt = f"""
Generate SEO keywords based on the strategy context and content calendar.

Content Calendar:
{content_calendar}

Create SEO inputs that support the blog articles, website copy, and content assets.

Include:
- Primary keywords
- Secondary keywords
- Long-tail keywords
- Search intent
- Suggested usage across content assets
- Priority level

Rules:
- Do not create a generic SEO plan.
- Do not invent unsupported search volume numbers.
- Keep keywords aligned with the strategy, ICP, personas, positioning, and market.
- Use B2B, enterprise-relevant keyword language.
"""

    return generate_content(strategy_context, prompt)



@tool
def generate_social_posts(strategy_context: str, content_calendar: str) -> str:
    """
    Generate ready-to-copy social media posts from the strategy and calendar.
    """

    prompt = f"""
Generate ready-to-copy social media posts based on the strategy context and content calendar.

Content Calendar:
{content_calendar}

Write 6 complete posts.

For each post include:
- Title
- Platform
- Target persona
- Funnel stage
- Full post copy
- CTA

Rules:
- Write actual post copy.
- Do not provide post ideas only.
- Do not provide instructions.
- Do not say what the team should write.
- Write the final copy directly.
- Adapt the message to the platform.
- Keep the tone B2B, credible, and enterprise-focused.
"""

    return generate_content(strategy_context, prompt)


@tool
def generate_email_campaign(strategy_context: str, content_calendar: str) -> str:
    """
    Generate a ready-to-copy B2B email sequence from the strategy and calendar.
    """

    prompt = f"""
Generate a ready-to-copy B2B email sequence based on the strategy context and content calendar.

Content Calendar:
{content_calendar}

Write 4 complete emails.

For each email include:
- Email number
- Target persona
- Funnel stage
- Subject line
- Preview text
- Full email body
- CTA

Rules:
- Write the actual email body.
- Do not provide summaries.
- Do not provide instructions.
- Do not say what the email should include.
- Write the final email copy directly.
- Keep the tone clear, credible, and enterprise-focused.
"""

    return generate_content(strategy_context, prompt)





@tool
def generate_ad_copy(strategy_context: str, content_calendar: str) -> str:
    """
    Generate ready-to-copy paid ad variations from the strategy and calendar.
    """

    prompt = f"""
Generate ready-to-copy paid ad variations based on the strategy context and content calendar.

Content Calendar:
{content_calendar}

Write 5 ad variations.

For each ad include:
- Platform
- Target persona
- Funnel stage
- Headline
- Primary text
- CTA

Rules:
- Write actual ad copy.
- Do not provide ad direction.
- Do not provide instructions.
- Keep copy concise and commercially useful.
- Avoid exaggerated or unsupported claims.
"""

    return generate_content(strategy_context, prompt)


@tool
def generate_blog_articles(strategy_context: str, content_calendar: str) -> str:
    """
    Generate ready-to-copy blog/article drafts from the strategy and calendar.
    """

    prompt = f"""
Generate 2 ready-to-copy B2B blog/article drafts based on the strategy context and content calendar.

Content Calendar:
{content_calendar}

For each article include:
- Article title
- Target persona
- Funnel stage
- Full article body
- CTA

Rules:
- Write the actual article draft.
- Do not provide only an outline.
- Do not provide a blog plan.
- Use clear H2/H3 headings.
- Keep the tone practical, credible, and enterprise-focused.
- Avoid unsupported statistics or exaggerated claims.
- Minimum 500 words per article.
"""

    return generate_content(strategy_context, prompt)




content_tools = [
    generate_content_calendar,
    generate_seo_keywords,
    generate_social_posts,
    generate_email_campaign,
    generate_ad_copy,
    generate_blog_articles,
]


content_agent = create_agent(
    model=llm,
    tools=content_tools,
    system_prompt=CONTENT_SYSTEM,
)


# =========================
# Output Helpers
# =========================

def build_content_assets(
    *,
    content_calendar: str,
    seo_keywords: str,
    social_posts: str,
    email_campaign: str,
    ad_copy: str,
    blog_articles: str,
) -> list[dict]:
    """
    Build UI-friendly content asset cards.
    """

    return [
        {
            "title": "Content Calendar",
            "content_type": "Calendar",
            "channel": "Multi-channel",
            "preview": "30-day content schedule generated from the GTM strategy.",
            "full_content": content_calendar,
            "cta": "Review schedule",
        },
        {
            "title": "SEO Keywords",
            "content_type": "SEO",
            "channel": "Search",
            "preview": "SEO keyword inputs generated to support content assets.",
            "full_content": seo_keywords,
            "cta": "Review keywords",
        },
        {
            "title": "Social Media Posts",
            "content_type": "Social Posts",
            "channel": "Social",
            "preview": "Ready-to-copy social posts generated from the strategy.",
            "full_content": social_posts,
            "cta": "Review posts",
        },
        {
            "title": "Email Campaign",
            "content_type": "Email",
            "channel": "Email",
            "preview": "Ready-to-copy B2B email sequence.",
            "full_content": email_campaign,
            "cta": "Review emails",
        },
        {
            "title": "Paid Ad Copy",
            "content_type": "Ads",
            "channel": "Paid Ads",
            "preview": "Ready-to-copy paid ad variations.",
            "full_content": ad_copy,
            "cta": "Review ads",
        },
        {
            "title": "Blog Articles",
            "content_type": "Blog",
            "channel": "Blog",
            "preview": "Ready-to-copy blog/article drafts.",
            "full_content": blog_articles,
            "cta": "Review articles",
        },
    ]
    
    
    
def assemble_content_assets_report(
    *,
    content_calendar: str,
    seo_keywords: str,
    social_posts: str,
    email_campaign: str,
    ad_copy: str,
    blog_articles: str,
) -> str:
    """
    Assemble final markdown report with calendar + ready-to-copy assets.
    """

    return f"""# Content Assets

## 1. Content Calendar
{content_calendar.strip()}

## 2. SEO Keywords
{seo_keywords.strip()}

## 3. Social Media Posts
{social_posts.strip()}

## 4. Email Campaign
{email_campaign.strip()}

## 5. Paid Ad Copy
{ad_copy.strip()}

## 6. Blog Articles
{blog_articles.strip()}
"""

def build_content_evidence(components: dict[str, Any]) -> dict:
    """
    Evidence bundle for guardrails factual-safety checks.
    """

    tool_outputs = []

    for tool_name, content in components.items():
        if tool_name == "content_assets":
            continue

        tool_outputs.append(
            {
                "tool": tool_name,
                "content": str(content)[:2000],
            }
        )

    return {
        "source": "strategy-aligned ready-to-copy content assets",
        "components": sorted(components.keys()),
        "tool_outputs": tool_outputs,
    }


# =========================
# Main ORCA Entry Point
# =========================

def run_content_agent_from_strategy(
    strategy_data: dict | str,
    memory_context: str = "",
    max_blog_posts: int | None = None,
) -> dict:
    """
    Run the Content Agent using Strategy Agent output.
    Generates a content calendar and ready-to-copy content assets.
    """

    print("[Content Agent] Running from Strategy Agent output...", flush=True)

    content_context = format_strategy_for_content(strategy_data)

    if memory_context:
        content_context = f"""
{content_context}

Relevant Long-Term Memory:
{memory_context}

Memory usage rule:
Use memory only for consistency and preferences. Current strategy is the source of truth.
"""

    print("[Content Agent] Generating content calendar...", flush=True)
    content_calendar = sanitize_content_language(
        generate_content_calendar.invoke(
            {
                "strategy_context": content_context,
            }
        )
    )
    
    print("[Content Agent] Generating SEO keywords...", flush=True)
    seo_keywords = sanitize_content_language(
        generate_seo_keywords.invoke(
            {
                "strategy_context": content_context,
                "content_calendar": content_calendar,
            }
        )
    )
    

    print("[Content Agent] Generating social posts...", flush=True)
    social_posts = sanitize_content_language(
        generate_social_posts.invoke(
            {
                "strategy_context": content_context,
                "content_calendar": content_calendar,
            }
        )
    )

    print("[Content Agent] Generating email campaign...", flush=True)
    email_campaign = sanitize_content_language(
        generate_email_campaign.invoke(
            {
                "strategy_context": content_context,
                "content_calendar": content_calendar,
            }
        )
    )

    print("[Content Agent] Generating ad copy...", flush=True)
    ad_copy = sanitize_content_language(
        generate_ad_copy.invoke(
            {
                "strategy_context": content_context,
                "content_calendar": content_calendar,
            }
        )
    )

    blog_count = max_blog_posts if max_blog_posts is not None else 2
    print(f"[Content Agent] Generating blog articles (count={blog_count})...", flush=True)
    blog_prompt = f"""
Generate {blog_count} ready-to-copy B2B blog/article drafts based on the strategy context and content calendar.

Content Calendar:
{content_calendar}

For each article include:
- Article title
- Target persona
- Funnel stage
- Full article body
- CTA

Rules:
- Write the actual article draft.
- Do not provide only an outline.
- Do not provide a blog plan.
- Use clear H2/H3 headings.
- Keep the tone practical, credible, and enterprise-focused.
- Avoid unsupported statistics or exaggerated claims.
- Minimum 500 words per article.
"""
    blog_articles = sanitize_content_language(
        generate_content(content_context, blog_prompt)
    )



    content_assets = build_content_assets(
    content_calendar=content_calendar,
    seo_keywords=seo_keywords,
    social_posts=social_posts,
    email_campaign=email_campaign,
    ad_copy=ad_copy,
    blog_articles=blog_articles,
)

    content_output = assemble_content_assets_report(
    content_calendar=content_calendar,
    seo_keywords=seo_keywords,
    social_posts=social_posts,
    email_campaign=email_campaign,
    ad_copy=ad_copy,
    blog_articles=blog_articles,
)

    components = {
    "content_calendar": content_calendar,
    "seo_keywords": seo_keywords,
    "social_posts": social_posts,
    "email_campaign": email_campaign,
    "ad_copy": ad_copy,
    "blog_articles": blog_articles,
    "content_assets": content_assets,
}

    evidence = build_content_evidence(components)

    results = {
        "agent": "content",
        "status": "completed",
        "generated_at": datetime.now().isoformat(),
        "input": {
            "strategy_data": strategy_data,
            "memory_used": bool(memory_context.strip()),
            "max_blog_posts": max_blog_posts,
        },
        "output": {
        "content_output": content_output,
        "content_calendar": content_calendar,
        "seo_keywords": seo_keywords,
        "content_assets": content_assets,
        "components": components,

        "social_posts": social_posts,
        "email_campaign": email_campaign,
        "ad_copy": ad_copy,
        "blog_articles": blog_articles,
},
        "evidence": evidence,
    }

    print("[Content Agent] Done.", flush=True)

    return results


# =========================
# Local Test Only
# =========================

if __name__ == "__main__":
    sample_strategy = {
        "output": {
            "strategy_output": """
Strategy placeholder for local testing.

Product:
BeamData AI Hub

Market:
Saudi Arabia

Audience:
Enterprise data, AI, and IT leaders

Positioning:
A practical enterprise AI platform for trusted knowledge access, chat, and agentic workflows.

Messaging pillars:
- Secure AI adoption
- Trusted enterprise knowledge
- Practical workflow automation
- Business-ready AI enablement

Channels:
LinkedIn, email, blog, paid ads, sales outreach
""",
            "brand_guidance": {
                "tone": "clear, credible, practical, enterprise-focused",
            },
        }
    }

    results = run_content_agent_from_strategy(sample_strategy)

    print("\nFINAL CONTENT OUTPUT:\n", flush=True)
    print(results["output"]["content_output"], flush=True)

if __name__ == "__main__":
    sample_strategy = {
        "output": {
            "strategy_output": "Paste Strategy Agent output here for local testing."
        }
    }

    results = run_content_agent_from_strategy(sample_strategy)

    print("\nFINAL CONTENT OUTPUT:\n", flush=True)
    print(results["output"]["content_output"], flush=True)