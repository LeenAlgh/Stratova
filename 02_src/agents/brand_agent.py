"""
Brand Alignment Agent — reviews Content Agent output against brand identity.

Designed for ORCA/LangGraph:
- Does NOT read content files.
- Does NOT save output files.
- Receives Content Agent output from LangGraph state.
- Optionally receives Strategy Agent output to use brand_guidance extracted by Strategy Agent.
- ORCA handles saving brand_alignment.json for Streamlit/FastAPI.
"""

import json
import os
import re
import sys
from datetime import datetime

from langchain.tools import tool

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENTS_DIR = os.path.dirname(os.path.abspath(__file__))

if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from knowledge_base.brand_identity import get_visual_system, load_brand_identity
from knowledge_base.rag import ask_with_context
from agents.content_utils import flatten_content_items, normalize_content_payload


BRAND_SYSTEM = """You are an expert Brand Alignment Agent for B2B technology companies.

You work AFTER the Content Agent in an ORCA/LangGraph workflow.
You receive Content Agent output through LangGraph state.
You may also receive Strategy Agent output that contains brand_guidance.

You do NOT read content files.
You do NOT save files.
You do NOT rewrite content.
You only evaluate whether the content is aligned with the brand identity and strategy.

Your job is to review content against:
1. Official brand identity guidelines
2. Brand guidance extracted by the Strategy Agent, if available
3. Strategy direction and positioning, if available

Review objectively and specifically.

You must evaluate:
- tone and voice
- positioning alignment
- messaging consistency
- vocabulary and terminology
- claims and exaggeration risk
- audience fit
- CTA fit
- platform/content format fit
- overall brand credibility

Rules:
- Do not rewrite the content.
- Do not create new content.
- Do not invent brand rules.
- If the content is off-brand, explain why.
- If content uses unsupported claims, flag them clearly using category descriptions — do not quote risky marketing phrases verbatim.
- If the content is strong, explain what makes it aligned.
- Use a score from 0 to 100.
- High alignment means score >= 70 and no critical brand violation.
- Low alignment means score < 70 or any critical brand violation.
"""


def parse_json_response(text: str) -> dict:
    """
    Parse model output into JSON.
    Handles markdown JSON fences if the model returns them.
    """

    cleaned = text.strip()

    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    return json.loads(cleaned)


def extract_brand_guidance_from_strategy(strategy_data: dict | None = None) -> dict:
    """
    Extract brand_guidance from Strategy Agent output if ORCA passes it.
    """

    if not strategy_data or isinstance(strategy_data, str):
        return {}

    output = strategy_data.get("output", strategy_data)

    return output.get("brand_guidance", {}) or {}


def build_brand_context(strategy_data: dict | None = None) -> str:
    """
    Build the full brand review context from the official brand identity document
    and optional Strategy Agent brand guidance.
    """

    identity = load_brand_identity()
    brand_guidance = extract_brand_guidance_from_strategy(strategy_data)

    parts = [
        "## Official Brand Identity Document",
        f"Source: {identity['doc_id']}",
        f"Pages: {identity['page_count']}",
        identity["formatted"][:12000],
    ]

    if brand_guidance:
        parts.append(
            "## Brand Guidance from Strategy Agent\n"
            + json.dumps(brand_guidance, indent=2, ensure_ascii=False)
        )

    return "\n\n".join(parts)


def extract_content_items(content_data: dict | str) -> list[dict]:
    """
    Convert Content Agent output into reviewable content items.
    Falls back to one item if content cannot be flattened.
    """

    if isinstance(content_data, str):
        return [
            {
                "id": "content_output",
                "type": "content_strategy",
                "title": "Content Agent Output",
                "body": content_data,
                "tags": ["Content Strategy"],
                "snippet": content_data[:220],
            }
        ]

    try:
        normalized = normalize_content_payload(content_data)
        items = flatten_content_items(normalized)
        if items:
            return items
    except Exception:
        pass

    output = content_data.get("output", content_data)

    if isinstance(output, dict):
        body = (
            output.get("content_output")
            or output.get("final_output")
            or json.dumps(output, indent=2, ensure_ascii=False)
        )
    else:
        body = str(output)

    return [
        {
            "id": "content_output",
            "type": "content_strategy",
            "title": "Content Agent Output",
            "body": body,
            "tags": ["Content Strategy"],
            "snippet": body[:220],
        }
    ]


@tool
def summarize_brand_guidelines(brand_context: str) -> str:
    """
    Summarize brand guidelines for UI display and review grounding.
    """

    prompt = """Summarize the key brand identity guidelines in 5-7 bullet points.
Cover: tone, voice, positioning, messaging do's/don'ts, vocabulary, and claims to avoid.
Keep each bullet practical for content review."""

    return ask_with_context(brand_context, prompt, system=BRAND_SYSTEM)


@tool
def evaluate_content_alignment(content_item: dict, brand_context: str) -> dict:
    """
    Score one content item against brand guidelines.
    """

    prompt = f"""Evaluate this content piece against the brand identity and brand guidance.

Content type:
{content_item.get("type")}

Title:
{content_item.get("title")}

Content:
{content_item.get("body", "")[:8000]}

Return ONLY valid JSON with this schema:
{{
  "alignment": "high" or "low",
  "score": 0,
  "strengths": ["..."],
  "gaps": ["..."],
  "unsupported_claims": ["..."],
  "brand_risks": ["..."],
  "recommendations": ["..."],
  "rationale": "1-2 sentence explanation"
}}

Rules:
- high = score >= 70 and no critical brand violation
- low = score < 70 or any critical brand violation
- Be specific.
- Reference content themes where useful, but do not quote risky marketing phrases verbatim.
- Do not rewrite the content.
- Flag unsupported claims by describing the issue (e.g. "absolutist accuracy promise") rather than repeating the phrase.
"""

    raw = ask_with_context(brand_context, prompt, system=BRAND_SYSTEM)

    try:
        result = parse_json_response(raw)
    except Exception:
        result = {
            "alignment": "low",
            "score": 0,
            "strengths": [],
            "gaps": ["Could not parse alignment evaluation."],
            "unsupported_claims": [],
            "brand_risks": [],
            "recommendations": [],
            "rationale": raw[:500],
        }

    score = result.get("score", 0)

    if score >= 70 and result.get("alignment") != "low":
        result["alignment"] = "high"
    else:
        result["alignment"] = "low"

    result["content_id"] = content_item.get("id")
    result["type"] = content_item.get("type")
    result["title"] = content_item.get("title")
    result["tags"] = content_item.get("tags") or [
        str(content_item.get("type", "Content")).title()
    ]
    result["snippet"] = content_item.get("snippet") or content_item.get("body", "")[:220]

    return result


@tool
def generate_alignment_summary(evaluations: list[dict], brand_context: str) -> dict:
    """
    Generate overall brand alignment summary from item evaluations.
    """

    high = [e for e in evaluations if e.get("alignment") == "high"]
    low = [e for e in evaluations if e.get("alignment") == "low"]
    total = len(evaluations)
    overall_score = (
        round(sum(e.get("score", 0) for e in evaluations) / total, 1)
        if total
        else 0
    )

    sanitized_evaluations = [
        {
            key: value
            for key, value in evaluation.items()
            if key not in {"body", "snippet"}
        }
        for evaluation in evaluations
    ]
    eval_blob = json.dumps(sanitized_evaluations, indent=2, ensure_ascii=False)

    prompt = f"""Write an executive summary of these brand alignment evaluations.

Evaluations:
{eval_blob}

Include:
- overall quality
- common strengths
- common brand gaps
- most important recommendations for the Content Agent

Keep it concise and practical.
Do not quote risky marketing phrases verbatim.
"""

    executive_summary = (
        ask_with_context(brand_context, prompt, system=BRAND_SYSTEM)
        if evaluations
        else ""
    )

    return {
        "high_count": len(high),
        "low_count": len(low),
        "total_items": total,
        "overall_score": overall_score,
        "executive_summary": executive_summary,
    }


def assemble_brand_alignment_report(
    brand_guidelines_summary: str,
    evaluations: list[dict],
    summary: dict,
) -> str:
    """Build a guardrails-friendly report without embedding raw off-brand content quotes."""

    lines = [
        "# Brand Alignment Report",
        "",
        "## Brand Guidelines Summary",
        brand_guidelines_summary.strip(),
        "",
        "## Content Evaluations and Scores",
        "",
    ]

    for evaluation in evaluations:
        title = evaluation.get("title", "Content Item")
        content_type = evaluation.get("type", "content")
        lines.append(f"### {title} ({content_type})")
        lines.append(f"- **Score:** {evaluation.get('score', 0)}")
        lines.append(f"- **Alignment:** {evaluation.get('alignment', 'unknown')}")

        for label, key in (
            ("Strengths", "strengths"),
            ("Gaps", "gaps"),
            ("Flagged claims in reviewed content", "unsupported_claims"),
            ("Brand risks", "brand_risks"),
            ("Recommendations", "recommendations"),
        ):
            values = evaluation.get(key) or []
            if values:
                lines.append(f"- **{label}:**")
                for value in values:
                    lines.append(f"  - {value}")
        if evaluation.get("rationale"):
            lines.append(f"- **Rationale:** {evaluation['rationale']}")
        lines.append("")

    strengths: list[str] = []
    gaps: list[str] = []
    recommendations: list[str] = []
    for evaluation in evaluations:
        strengths.extend(evaluation.get("strengths") or [])
        gaps.extend(evaluation.get("gaps") or [])
        recommendations.extend(evaluation.get("recommendations") or [])

    unique_strengths = list(dict.fromkeys(strengths))[:12]
    unique_gaps = list(dict.fromkeys(gaps))[:12]
    unique_recommendations = list(dict.fromkeys(recommendations))[:12]

    lines.extend(["", "## Strengths", ""])
    if unique_strengths:
        lines.extend(f"- {item}" for item in unique_strengths)
    else:
        lines.append("- None noted.")

    lines.extend(["", "## Gaps", ""])
    if unique_gaps:
        lines.extend(f"- {item}" for item in unique_gaps)
    else:
        lines.append("- None noted.")

    lines.extend(["", "## Recommendations", ""])
    if unique_recommendations:
        lines.extend(f"- {item}" for item in unique_recommendations)
    else:
        lines.append("- None noted.")

    lines.extend(
        [
            "",
            "## Executive Summary",
            f"- **Overall score:** {summary.get('overall_score', 0)}",
            f"- **High alignment items:** {summary.get('high_count', 0)}",
            f"- **Low alignment items:** {summary.get('low_count', 0)}",
            f"- **Total items reviewed:** {summary.get('total_items', 0)}",
            "",
            (summary.get("executive_summary") or "").strip(),
        ]
    )

    return "\n".join(lines).strip()


def build_brand_evidence(
    *,
    brand_context: str,
    evaluations: list[dict],
    content_data: dict | str | None,
) -> dict:
    """Evidence bundle for guardrails checks."""

    content_items = []
    if isinstance(content_data, dict):
        content_evidence = content_data.get("evidence")
        if content_evidence:
            content_items.append(content_evidence)

    return {
        "source": "brand identity document and reviewed content metadata",
        "brand_context_excerpt": brand_context[:3000],
        "reviewed_items": [
            {
                "id": item.get("id"),
                "type": item.get("type"),
                "title": item.get("title"),
                "score": item.get("score"),
                "alignment": item.get("alignment"),
            }
            for item in evaluations
        ],
        "content_evidence": content_items,
    }


brand_tools = [
    summarize_brand_guidelines,
    evaluate_content_alignment,
    generate_alignment_summary,
]


def run_brand_agent_from_content(
    content_data: dict | str,
    strategy_data: dict | None = None,
) -> dict:
    """
    Run the Brand Alignment Agent using Content Agent output from LangGraph state.

    Args:
        content_data: Content Agent output passed from ORCA/LangGraph.
        strategy_data: Optional Strategy Agent output containing brand_guidance.

    Returns:
        dict with brand alignment review. ORCA is responsible for saving this.
    """

    print("[Brand Agent] Running from Content Agent output...", flush=True)

    brand_context = build_brand_context(strategy_data)

    brand_guidelines_summary = summarize_brand_guidelines.invoke(
        {
            "brand_context": brand_context
        }
    )

    items = extract_content_items(content_data)

    print(f"[Brand Agent] Evaluating {len(items)} content item(s)...", flush=True)

    evaluations = []

    for item in items:
        print(f"[Brand Agent] Reviewing: {item.get('title')}", flush=True)

        evaluation = evaluate_content_alignment.invoke(
            {
                "content_item": item,
                "brand_context": brand_context,
            }
        )

        evaluations.append(evaluation)

    summary = generate_alignment_summary.invoke(
        {
            "evaluations": evaluations,
            "brand_context": brand_context,
        }
    )

    high_alignment = [e for e in evaluations if e.get("alignment") == "high"]
    low_alignment = [e for e in evaluations if e.get("alignment") == "low"]

    brand_alignment_output = assemble_brand_alignment_report(
        brand_guidelines_summary=brand_guidelines_summary,
        evaluations=evaluations,
        summary=summary,
    )
    evidence = build_brand_evidence(
        brand_context=brand_context,
        evaluations=evaluations,
        content_data=content_data,
    )

    results = {
        "agent": "brand_alignment",
        "status": "completed",
        "generated_at": datetime.now().isoformat(),
        "input": {
            "content_data": content_data,
            "strategy_data": strategy_data,
        },
        "output": {
            "brand_alignment_output": brand_alignment_output,
            "brand_visual_system": get_visual_system(),
            "brand_guidelines_summary": brand_guidelines_summary,
            "evaluations": evaluations,
            "summary": summary,
            "high_alignment": high_alignment,
            "low_alignment": low_alignment,
        },
        "evidence": evidence,
    }

    print("[Brand Agent] Done.", flush=True)

    return results


if __name__ == "__main__":
    sample_content = {
        "output": {
            "content_output": "Paste Content Agent output here for local testing."
        }
    }

    results = run_brand_agent_from_content(sample_content)

    print("\nFINAL BRAND ALIGNMENT OUTPUT:\n", flush=True)
    print(json.dumps(results["output"]["summary"], indent=2, ensure_ascii=False), flush=True)