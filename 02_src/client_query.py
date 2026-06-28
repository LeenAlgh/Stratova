"""Build canonical GTM brief strings for ORCA and the research agent."""

from __future__ import annotations

from langchain_core.tools import tool

DEFAULT_GTM_BRIEF: dict[str, str] = {
    "product": (
        "Lumora Pipeline Copilot — a revenue-intelligence module that auto-instruments "
        "CRM data and flags at-risk deals, from a mid-market RevOps platform."
    ),
    "market": (
        "Revenue intelligence / RevOps, North America, crowded with enterprise "
        "incumbents that require long implementations."
    ),
    "audience": (
        "Mid-market B2B SaaS RevOps leaders (200–2,000 employees) who own forecast "
        "accuracy but lack engineering support and fear another failed rollout."
    ),
    "goals": "Drive qualified free-trial signups in the first 30 days",
}

GTM_BRIEF_FIELDS = ("product", "audience", "market", "goals")


def _section(label: str, value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    return f"{label}:\n{text}"


def build_user_input(
    *,
    product: str,
    market: str,
    audience: str,
    goals: str = "",
) -> str:
    """Format sidebar/API fields into the ORCA user_input contract."""
    sections = [
        "Research the GTM opportunity.",
        "",
        _section("Product", product),
        _section("Market", market),
        _section("Audience", audience),
        _section("Goals", goals),
    ]
    return "\n\n".join(part for part in sections if part)


def build_user_input_from_config(config: dict) -> str:
    """Map a {product, market, audience, goals} dict to user_input."""
    return build_user_input(
        product=config.get("product", ""),
        market=config.get("market", ""),
        audience=config.get("audience", ""),
        goals=config.get("goals", ""),
    )


def validate_gtm_brief(product: str, audience: str) -> list[str]:
    """Return validation error messages (empty list means valid)."""
    errors: list[str] = []
    if not (product or "").strip():
        errors.append("Product is required.")
    if not (audience or "").strip():
        errors.append("Audience is required.")
    return errors


@tool
def build_gtm_query(
    product: str,
    audience: str,
    market: str = "",
    goals: str = "",
) -> str:
    """Build the labeled GTM brief string for ORCA and the research agent."""
    return build_user_input(
        product=product,
        market=market,
        audience=audience,
        goals=goals,
    )
