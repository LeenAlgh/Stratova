"""
Memory System for Stratova GTM Multi-Agent Workflow.

Current core workflow:
Research -> Strategy -> Content -> Brand Alignment

Memory layers:
1. Short-term memory: LangGraph state during one ORCA run.
2. Long-term memory: PostgreSQL through postgres_memory.py.

This module connects ORCA state with PostgreSQL memory.
"""

import json
import re
from datetime import datetime
from typing import Any, TypedDict

import postgres_memory


# =========================
# Short-term memory schema
# =========================

class ShortTermMemory(TypedDict, total=False):
    current_campaign_objective: str
    user_input: str
    selected_product: str
    selected_market: str
    selected_audience: str
    selected_market_segment: str
    active_strategy_draft: str
    latest_research_summary: str
    latest_content_summary: str
    latest_brand_alignment_summary: str
    guardrails_summary: dict
    created_at: str
    updated_at: str


# =========================
# Helper functions
# =========================

def now_iso() -> str:
    return datetime.now().isoformat()


def make_json_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, indent=2, ensure_ascii=False)


def summarize_text(text: str, max_chars: int = 900) -> str:
    clean = re.sub(r"\s+", " ", text or "").strip()
    if len(clean) <= max_chars:
        return clean
    return clean[:max_chars].rstrip() + "..."


def extract_primary_text(data: Any) -> str:
    """Extract main text from agent output."""

    if data is None:
        return ""

    if isinstance(data, str):
        return data

    if not isinstance(data, dict):
        return str(data)

    output = data.get("output", data)

    if isinstance(output, str):
        return output

    if not isinstance(output, dict):
        return make_json_text(output)

    keys = [
        "research_output",
        "strategy_output",
        "content_output",
        "brand_guidelines_summary",
        "final_report",
        "final_output",
    ]

    for key in keys:
        if isinstance(output.get(key), str):
            return output[key]

    if isinstance(output.get("summary"), dict):
        summary = output["summary"]
        if isinstance(summary.get("executive_summary"), str):
            return summary["executive_summary"]

    return make_json_text(output)


def extract_field_from_user_input(user_input: str, label: str) -> str:
    """
    Extract simple labeled values from user input like:
    Product:
    Market:
    Audience:
    """

    pattern = rf"{label}\s*:\s*(.+?)(?:\n\n|\n[A-Z][A-Za-z /]+\s*:|$)"
    match = re.search(pattern, user_input, flags=re.IGNORECASE | re.DOTALL)

    if not match:
        return ""

    return match.group(1).strip()


# =========================
# Short-term memory
# =========================

def initialize_short_term_memory(user_input: str) -> ShortTermMemory:
    """Initialize ORCA short-term memory from the user request."""

    product = extract_field_from_user_input(user_input, "Product")
    market = extract_field_from_user_input(user_input, "Market")
    audience = extract_field_from_user_input(user_input, "Audience")
    goals = extract_field_from_user_input(user_input, "Goals")

    campaign_objective = goals or summarize_text(user_input, max_chars=500)

    return {
        "current_campaign_objective": campaign_objective,
        "user_input": user_input,
        "selected_product": product,
        "selected_market": market,
        "selected_audience": audience,
        "selected_market_segment": " | ".join(
            part for part in [product, market, audience] if part
        ),
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }


def update_short_term_memory(
    short_term_memory: dict | None = None,
    research_data: dict | None = None,
    strategy_data: dict | None = None,
    content_data: dict | None = None,
    brand_alignment_data: dict | None = None,
    guardrails_results: dict | None = None,
) -> ShortTermMemory:
    """Update ORCA short-term memory as each agent completes."""

    memory = dict(short_term_memory or {})

    if research_data:
        memory["latest_research_summary"] = summarize_text(
            extract_primary_text(research_data),
            max_chars=1000,
        )

    if strategy_data:
        strategy_text = extract_primary_text(strategy_data)
        memory["active_strategy_draft"] = summarize_text(strategy_text, max_chars=1200)

    if content_data:
        memory["latest_content_summary"] = summarize_text(
            extract_primary_text(content_data),
            max_chars=1000,
        )

    if brand_alignment_data:
        memory["latest_brand_alignment_summary"] = summarize_text(
            extract_primary_text(brand_alignment_data),
            max_chars=900,
        )

    if guardrails_results:
        memory["guardrails_summary"] = {
            agent: {
                "status": result.get("status"),
                "score": result.get("score"),
            }
            for agent, result in guardrails_results.items()
            if isinstance(result, dict)
        }

    memory["updated_at"] = now_iso()

    return memory


# =========================
# Long-term memory
# =========================

def initialize_long_term_memory() -> None:
    """Initialize PostgreSQL memory tables."""

    postgres_memory.init_memory_db()


def save_long_term_memory_from_state(run_state: dict) -> dict:
    """Save completed ORCA run to PostgreSQL memory."""

    return postgres_memory.save_completed_run_from_state(run_state)


def build_long_term_memory_context(
    user_input: str,
    agent_name: str | None = None,
    limit: int = 5,
) -> str:
    """Retrieve relevant long-term memory from PostgreSQL."""

    return postgres_memory.build_memory_context(
        user_input=user_input,
        agent_name=agent_name,
        limit=limit,
    )


def build_agent_context_with_memory(
    user_input: str,
    agent_name: str,
    short_term_memory: dict | None = None,
    limit: int = 5,
) -> str:
    """
    Build memory context for an agent.

    Current user input and LangGraph state remain the source of truth.
    Memory is supporting context only.
    """

    long_term_memory = build_long_term_memory_context(
        user_input=user_input,
        agent_name=agent_name,
        limit=limit,
    )

    return f"""
## Memory Instructions
Use memory only as supporting context.
Do not override the current user input or current LangGraph state.

## Current Short-Term Memory
{json.dumps(short_term_memory or {}, indent=2, ensure_ascii=False)}

## Relevant Long-Term Memory
{long_term_memory}
"""


# =========================
# ORCA helper
# =========================

def prepare_initial_memory_state(user_input: str) -> dict:
    """Prepare memory fields for initial ORCA state."""

    initialize_long_term_memory()

    short_term_memory = initialize_short_term_memory(user_input)

    memory_context = build_agent_context_with_memory(
        user_input=user_input,
        agent_name="research",
        short_term_memory=short_term_memory,
        limit=5,
    )

    return {
        "short_term_memory": short_term_memory,
        "memory_context": memory_context,
    }


def update_memory_after_agent(
    state: dict,
    agent_name: str,
    agent_data: dict,
) -> dict:
    """Update short-term memory after an agent finishes."""

    kwargs = {
        "short_term_memory": state.get("short_term_memory"),
        "guardrails_results": state.get("guardrails_results"),
    }

    if agent_name == "research":
        kwargs["research_data"] = agent_data
    elif agent_name == "strategy":
        kwargs["strategy_data"] = agent_data
    elif agent_name == "content":
        kwargs["content_data"] = agent_data
    elif agent_name == "brand_alignment":
        kwargs["brand_alignment_data"] = agent_data

    return update_short_term_memory(**kwargs)


if __name__ == "__main__":
    initialize_long_term_memory()
    print("Memory system ready.")
