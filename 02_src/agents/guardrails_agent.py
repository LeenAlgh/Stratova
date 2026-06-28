"""
Guardrails Agent — evaluates each agent output against its role and rules.

Purpose:
- Acts like an agent evaluator.
- Does NOT rewrite outputs.
- Does NOT save files.
- ORCA can call it after each agent node.
- Returns pass/fail, score, violations, and recommendations.

Designed for ORCA/LangGraph:
- Pipeline data remains in state.
- ORCA may save guardrail results for Streamlit UI.
"""

import json
import os
import re
import sys
from datetime import datetime
from typing import Any

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from knowledge_base.rag import ask_with_context


GUARDRAILS_SYSTEM = """You are a fair Guardrails Evaluation Agent for a GTM multi-agent system.

Your job is to evaluate whether an agent output follows its assigned role, input constraints, and output requirements.

You do NOT rewrite the output.
You do NOT generate missing content.
You only evaluate, score, and explain violations.

Return objective feedback.
Be fair and calibrated:
- Reward complete, well-structured outputs that include required sections.
- Do not penalize research channel insights; researching channels is in scope.
- Do not penalize strategy or content agents for doing their core job.
- Treat statistics labeled (estimate), (assumption), or with a source citation as acceptable.
- When evidence is provided, assume figures derived from that evidence are supported.

If the output is only a success message instead of the required report, mark it as fail.
If the output invents unsupported facts with no label or evidence, mark factual_safety down.
If the output clearly performs another agent's job (e.g. full campaign copy in research), mark role_compliance down.
"""


AGENT_GUARDRAILS = {
    "research": {
        "role": "Research Agent",
        "allowed": [
            "Define market scope",
            "Gather company knowledge",
            "Perform market and competitor research",
            "Analyze audience and channels",
            "Summarize findings for Strategy Agent",
        ],
        "not_allowed": [
            "Create final GTM strategy",
            "Write full content campaigns",
            "Update strategy based on performance",
            "Invent market facts without stating assumptions",
        ],
        "required_output": [
            "market scope",
            "company context",
            "market insights",
            "competitor insights",
            "audience insights",
            "channel insights",
            "takeaways for Strategy Agent",
        ],
    },
    "strategy": {
        "role": "Strategy Agent",
        "allowed": [
            "Turn research into GTM strategy",
            "Create ICP, personas, positioning, messaging pillars, channels, and 90-day plan",
            "Use brand guidance",
            "Create handoff notes for Content Agent",
        ],
        "not_allowed": [
            "Perform new market research",
            "Generate full social posts, blogs, or email campaigns",
            "Ignore brand guidance",
            "Use exaggerated or unsupported claims",
            "Update previous strategy based on performance data",
        ],
        "required_output": [
            "executive summary",
            "ICP",
            "buyer personas",
            "positioning",
            "messaging pillars",
            "channel strategy",
            "90-day GTM plan",
            "metrics",
            "handoff to Content Agent",
        ],
    },
    "content": {
        "role": "Content Agent",
        "allowed": [
            "Turn approved strategy into ready-to-copy content assets",
            "Create a content calendar as a publishing schedule",
            "Generate SEO keywords that support content assets",
            "Generate ready-to-copy social posts",
            "Generate ready-to-copy email bodies",
            "Generate ready-to-copy paid ad copy",
            "Generate ready-to-copy blog/article drafts",
            "Follow brand guidance and approved strategy",
        ],
        "not_allowed": [
            "Create a new GTM strategy",
            "Change positioning without evidence",
            "Perform market research",
            "Use unsupported claims",
            "Return only plans, directions, summaries, or instructions instead of actual content",
            "Return only a success message instead of actual content",
            "Generate sales enablement copy or objection responses if not requested",
        ],
        "required_output": [
            "Content Calendar",
            "SEO Keywords",
            "Social Media Posts",
            "Email Campaign",
            "Paid Ad Copy",
            "Blog Articles",
        ],
    },
    "brand_alignment": {
        "role": "Brand Alignment Agent",
        "allowed": [
            "Evaluate content against brand identity",
            "Score alignment",
            "Identify strengths, gaps, unsupported claims, and brand risks",
            "Summarize high and low alignment items",
        ],
        "not_allowed": [
            "Rewrite content",
            "Create new content",
            "Change the strategy",
            "Ignore official brand guidelines",
        ],
        "required_output": [
            "brand guidelines summary",
            "evaluations",
            "scores",
            "strengths",
            "gaps",
            "recommendations",
            "summary",
        ],
    },
    "analysis": {
        "role": "Analysis Agent",
        "allowed": [
            "Analyze campaign performance",
            "Calculate campaign metrics",
            "Evaluate campaign effectiveness",
            "Identify strengths and weaknesses",
            "Generate performance insights",
        ],
        "not_allowed": [
            "Create optimization recommendations",
            "Update GTM strategy",
            "Generate marketing content",
            "Perform new market research",
            "Modify campaign plans",
        ],
        "required_output": [
            "performance summary",
            "CTR analysis",
            "engagement analysis",
            "lead analysis",
            "conversion analysis",
            "ROI analysis",
            "strengths",
            "weaknesses",
            "key insights",
        ],
    },
}


FORBIDDEN_CLAIM_PATTERNS = [
    r"\bguaranteed\b",
    r"\b100%\b",
    r"\binstant(?:ly)?\b",
    r"\blimitless\b",
    r"\brevolutioniz(?:e|ing|es) everything\b",
    r"\bworld[- ]class\b",
    r"\bbest[- ]in[- ]class\b",
    r"\b#1\b",
]

FORBIDDEN_CLAIM_NEGATION = re.compile(
    r"\b(claims?\s+to\s+avoid|avoid|do\s+not|don't|never|not\s+to|such\s+as|example|e\.g\.)\b",
    re.IGNORECASE,
)


def find_forbidden_claim_violations(output_text: str) -> list[str]:
    """
    Detect risky marketing phrases, ignoring lines that warn against using them.
    """

    violations: list[str] = []
    in_avoid_section = False

    for line in output_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        lower = stripped.lower()

        if re.search(r"claims?\s+to\s+avoid", lower):
            in_avoid_section = True

        if re.match(r"^#{1,6}\s", stripped):
            if not re.search(r"claims?\s+to\s+avoid", lower):
                in_avoid_section = False

        scan_line = stripped
        if in_avoid_section:
            continue

        if FORBIDDEN_CLAIM_NEGATION.search(lower):
            scan_line = re.sub(r'"[^"]*"|\'[^\']*\'', "", stripped)
            if not scan_line.strip():
                continue

        for pattern in FORBIDDEN_CLAIM_PATTERNS:
            if re.search(pattern, scan_line, flags=re.IGNORECASE):
                violations.append(pattern)

    return list(dict.fromkeys(violations))


def make_json_text(value: Any) -> str:
    if value is None:
        return "Not provided."
    if isinstance(value, str):
        return value
    return json.dumps(value, indent=2, ensure_ascii=False)


def parse_json_response(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned)


def extract_primary_output_text(output_data: dict | str | None) -> str:
    if output_data is None:
        return ""

    if isinstance(output_data, str):
        return output_data

    output = output_data.get("output", output_data)

    if isinstance(output, str):
        return output

    if not isinstance(output, dict):
        return make_json_text(output)

    possible_keys = [
        "brand_alignment_output",
        "research_output",
        "strategy_output",
        "content_output",
        "analysis_output",
        "analysis_report",
        "update_optimization_output",
        "final_report",
        "brand_guidelines_summary",
    ]

    for key in possible_keys:
        if isinstance(output.get(key), str):
            return output[key]

    return make_json_text(output)


def extract_evidence_context(
    input_data: dict | str | None,
    output_data: dict | str | None,
) -> str:
    """Gather tool/source evidence from agent input and output payloads."""

    evidence_parts: list[str] = []

    def collect_from_payload(payload: dict | str | None) -> None:
        if not isinstance(payload, dict):
            return

        evidence = payload.get("evidence")
        if evidence:
            evidence_parts.append(make_json_text(evidence))

        research_data = payload.get("research_data")
        if isinstance(research_data, dict):
            nested_evidence = research_data.get("evidence")
            if nested_evidence:
                evidence_parts.append(make_json_text(nested_evidence))

        strategy_data = payload.get("strategy_data")
        if isinstance(strategy_data, dict):
            nested_evidence = strategy_data.get("evidence")
            if nested_evidence:
                evidence_parts.append(make_json_text(nested_evidence))

            strategy_output = strategy_data.get("output", {})
            if isinstance(strategy_output, dict):
                strategy_text = strategy_output.get("strategy_output")
                if isinstance(strategy_text, str) and strategy_text.strip():
                    evidence_parts.append(
                        "Approved strategy context:\n" + strategy_text[:6000]
                    )

        content_data = payload.get("content_data")
        if isinstance(content_data, dict):
            nested_evidence = content_data.get("evidence")
            if nested_evidence:
                evidence_parts.append(make_json_text(nested_evidence))

        analysis_data = payload.get("analysis_data")
        if isinstance(analysis_data, dict):
            nested_evidence = analysis_data.get("evidence")
            if nested_evidence:
                evidence_parts.append(make_json_text(nested_evidence))

    collect_from_payload(output_data if isinstance(output_data, dict) else None)
    collect_from_payload(input_data if isinstance(input_data, dict) else None)

    if not evidence_parts:
        return "Not provided."

    combined = "\n\n".join(evidence_parts)
    return combined[:12000]


AGENT_EVALUATION_NOTES = {
    "research": (
        "Channel insights and competitor analysis are required research responsibilities — "
        "they are NOT Strategy Agent work. "
        "Takeaways for the Strategy Agent must be observational findings only, not campaign plans."
    ),
    "strategy": (
        "Producing a full GTM strategy with ICP, personas, positioning, messaging pillars, "
        "channel strategy, and a 90-day plan is this agent's core job. Do not penalize "
        "completeness or strategic recommendations that stay within that scope."
    ),
    "content": (
    "The Content Agent should generate a content calendar, SEO keywords, and ready-to-copy "
    "marketing assets. The calendar is allowed because it is a publishing schedule. "
    "SEO keywords are allowed because they support content creation. "
    "Social posts, emails, ads, and blogs must be actual usable content, not only plans, "
    "directions, summaries, or instructions. "
    "Do not require Sales Enablement Copy or Objection Responses. "
    "Penalize if the output is mostly planning language, if emails are only summaries, "
    "if ads are only directions, or if social posts are only ideas."
),
    "brand_alignment": (
        "Evaluating brand alignment, scoring content, and listing gaps is this agent's job. "
        "Flagging unsupported or risky claims found IN reviewed content is required — that is "
        "not a factual-safety violation by this agent. "
        "Do not penalize the agent for describing content risks using neutral review language."
    ),
    "analysis": (
        "The Analysis Agent is responsible for evaluating campaign performance "
        "using available metrics and generating objective performance insights. "
        "It may calculate CTR, engagement rate, conversion rate, ROI, CPL, CPA, "
        "and other campaign KPIs. "
        "Do not penalize the agent for reporting performance results. "
        "Penalize only if it generates optimization recommendations, "
        "updates GTM strategy, or creates marketing content."
    ),
}


SECTION_ALIASES: dict[str, dict[str, list[str]]] = {
    "research": {
        "market scope": [r"market\s*scope"],
        "company context": [r"company\s*context"],
        "market insights": [r"market\s*insights", r"market\s*overview"],
        "competitor insights": [r"competitor"],
        "audience insights": [r"audience"],
        "channel insights": [r"channel"],
        "takeaways for Strategy Agent": [r"takeaways?\s+for\s+strategy"],
    },
    "strategy": {
        "executive summary": [r"executive\s*summary"],
        "ICP": [r"\bicp\b", r"ideal\s*customer", r"firmographics"],
        "buyer personas": [r"persona"],
        "positioning": [r"positioning"],
        "messaging pillars": [r"messaging\s*pillar", r"pillar\s*\d"],
        "channel strategy": [r"channel\s*strategy", r"recommended\s*channels"],
        "90-day GTM plan": [r"90[- ]day", r"30[- ]day", r"month\s*1", r"gtm\s*plan"],
        "metrics": [r"metrics"],
        "handoff to Content Agent": [r"handoff", r"content\s*agent"],
    },
    "content": {
    "Content Calendar": [r"content\s*calendar",r"30[- ]day\s*content",r"publishing\s*schedule",],
    "SEO Keywords": [r"seo\s*keywords?",r"primary\s*keywords?",r"secondary\s*keywords?",r"long[- ]tail\s*keywords?",r"search\s*intent",],
    "Social Media Posts": [r"social\s*media\s*posts?",r"social\s*posts?",r"full\s*post\s*copy",r"post\s*copy",
    ],
    "Email Campaign": [
        r"email\s*campaign",
        r"email\s*sequence",
        r"subject\s*line",
        r"preview\s*text",
        r"full\s*email\s*body",
    ],
    "Paid Ad Copy": [
        r"paid\s*ad\s*copy",
        r"ad\s*copy",
        r"headline",
        r"primary\s*text",
    ],
    "Blog Articles": [
        r"blog\s*articles?",
        r"article\s*title",
        r"full\s*article\s*body",
        r"blog/article\s*drafts?",
    ],
},
    "brand_alignment": {
        "brand guidelines summary": [r"brand\s*guidelines\s*summary"],
        "evaluations": [r"evaluations?\s+and\s+scores", r"content\s*evaluations"],
        "scores": [r"\bscore\b", r"overall\s*score"],
        "strengths": [r"strengths"],
        "gaps": [r"\bgaps\b"],
        "recommendations": [r"recommendations"],
        "summary": [r"executive\s*summary"],
    },
    "analysis": {
        "performance summary": [r"performance\s*summary"],
        "CTR analysis": [r"ctr\s*analysis", r"\bctr\b"],
        "engagement analysis": [r"engagement\s*analysis", r"engagement\s*rate"],
        "lead analysis": [r"lead\s*analysis", r"\bleads?\b"],
        "conversion analysis": [r"conversion\s*analysis", r"conversion\s*rate"],
        "ROI analysis": [r"roi\s*analysis", r"\broi\b"],
        "strengths": [r"strengths"],
        "weaknesses": [r"weaknesses"],
        "key insights": [r"key\s*insights"],
    },
}


CITATION_MARKERS = re.compile(
    r"\(estimate\)|\(assumption\)|\(source[:\)]|source:|https?://|per web search|labeled as estimate",
    re.IGNORECASE,
)
STAT_LINE_PATTERN = re.compile(r"\d+(?:\.\d+)?%|usd\s*\d|cagr|\$\d", re.IGNORECASE)
RESEARCH_ACTION_PATTERN = re.compile(
    r"\b(invest in|launch a|launch the|create a campaign|run a campaign|utilize linkedin for|implement a marketing)\b",
    re.IGNORECASE,
)
CONTENT_NEW_RESEARCH_PATTERN = re.compile(
    r"\b(cagr|market\s+size|usd\s+\d|billion\s+by\s+20\d{2})\b",
    re.IGNORECASE,
)
ANALYSIS_ROLE_VIOLATION_PATTERN = re.compile(
    r"\b("
    r"optimization recommendation|recommended optimization|"
    r"update (the )?gtm strategy|rewrite (the )?strategy|"
    r"generate (social|email|blog|ad)|create (new )?marketing content|"
    r"perform new market research|modify (the )?campaign plan"
    r")\b",
    re.IGNORECASE,
)

CONTENT_BAD_PATTERNS = [
    "you should",
    "the team should",
    "recommended approach",
    "content idea",
    "content ideas",
    "campaign plan",
    "email body summary",
    "ad copy direction",
    "blog plan",
    "suggested topic",
    "write a post about",
    "sales enablement",
    "objection response",
]

CONTENT_GOOD_PATTERNS = [
    "full post copy",
    "subject line",
    "preview text",
    "full email body",
    "headline",
    "primary text",
    "cta",
    "article title",
    "full article body",
]



def deterministic_checks(agent_name: str, output_text: str) -> dict:
    """
    Fast checks before LLM evaluation.
    """

    issues = []

    if not output_text or len(output_text.strip()) < 100:
        issues.append("Output is too short or empty.")

    success_only_patterns = [
        "has been successfully created",
        "if you need any further modifications",
        "feel free to ask",
        "successfully completed",
    ]

    lowered = output_text.lower()

    if any(pattern in lowered for pattern in success_only_patterns) and len(output_text) < 1000:
        issues.append("Output looks like a success confirmation, not the required report.")

    forbidden_claims = []
    if agent_name != "brand_alignment":
        forbidden_claims = find_forbidden_claim_violations(output_text)

    if forbidden_claims:
        issues.append("Output contains exaggerated or risky claims.")

    return {
        "issues": issues,
        "forbidden_claim_patterns": forbidden_claims,
        "passed_fast_checks": len(issues) == 0,
        "critical": (
            not output_text
            or len(output_text.strip()) < 100
            or (
                any(pattern in lowered for pattern in success_only_patterns)
                and len(output_text) < 1000
            )
        ),
    }

def evaluate_ready_to_copy_content(output_text: str) -> dict:
    """
    Checks whether Content Agent output is actual ready-to-copy content
    or still planning/instructional language.
    """

    text = output_text.lower()

    bad_hits = [
        pattern for pattern in CONTENT_BAD_PATTERNS
        if pattern.lower() in text
    ]

    good_hits = [
        pattern for pattern in CONTENT_GOOD_PATTERNS
        if pattern.lower() in text
    ]

    issues = []

    if len(bad_hits) >= 3:
        issues.append(
            "Content output contains planning or instruction-style language instead of ready-to-copy assets."
        )

    if "sales enablement" in bad_hits or "objection response" in bad_hits:
        issues.append(
            "Content output includes Sales Enablement Copy or Objection Response, which is not required in the current Content Agent scope."
        )

    return {
        "bad_hits": bad_hits,
        "good_hits": good_hits,
        "issues": issues,
        "passed": len(issues) == 0,
    }
    
    
    
def _has_any_key(payload: dict, keys: list[str]) -> bool:
    """Return True if any key exists and has a non-empty value."""

    for key in keys:
        value = payload.get(key)
        if value:
            return True
    return False


def _extract_brand_alignment_inner(output_data: dict | str | None) -> dict:
    """Return the most likely structured brand-alignment payload."""

    if not isinstance(output_data, dict):
        return {}

    inner = output_data.get("output", output_data)
    if isinstance(inner, dict):
        return inner

    return {}


def _extract_evaluations(inner: dict) -> list:
    """Support different possible names for content-level brand evaluations."""

    for key in [
        "evaluations",
        "content_evaluations",
        "alignment_items",
        "content_alignment_items",
        "content_alignment_gallery",
        "items",
    ]:
        value = inner.get(key)
        if isinstance(value, list):
            return value

    return []


def score_brand_structural_completeness(output_data: dict | str | None) -> tuple[int, list[str]]:
    """Check brand alignment payload structure directly."""

    inner = _extract_brand_alignment_inner(output_data)
    if not inner:
        return 0, ["structured output"]

    missing: list[str] = []

    has_brand_guidelines = _has_any_key(
        inner,
        [
            "brand_guidelines_summary",
            "brand_guidelines",
            "brand_identity",
            "brand_assets",
            "brand_profile",
        ],
    )

    if not has_brand_guidelines:
        missing.append("brand guidelines summary")

    # If the page/agent exposes visual identity fields, count them as brand guideline support.
    has_visual_identity = (
        _has_any_key(inner, ["logo", "logo_path", "colors", "fonts"])
        or (
            isinstance(inner.get("brand_guidelines"), dict)
            and _has_any_key(inner["brand_guidelines"], ["logo", "logo_path", "colors", "fonts"])
        )
        or (
            isinstance(inner.get("brand_identity"), dict)
            and _has_any_key(inner["brand_identity"], ["logo", "logo_path", "colors", "fonts"])
        )
    )

    # Visual identity is useful but not mandatory for passing guardrails.
    evaluations = _extract_evaluations(inner)

    if not evaluations:
        missing.append("evaluations")
    else:
        if not any(isinstance(item, dict) and ("score" in item or "alignment_score" in item) for item in evaluations):
            missing.append("scores")
        if not any(isinstance(item, dict) and (item.get("strengths") or item.get("brand_strengths")) for item in evaluations):
            missing.append("strengths")
        if not any(isinstance(item, dict) and (item.get("gaps") or item.get("weaknesses") or item.get("risks")) for item in evaluations):
            missing.append("gaps")
        if not any(isinstance(item, dict) and (item.get("recommendations") or item.get("improvement_note")) for item in evaluations):
            missing.append("recommendations")

    if not _has_any_key(inner, ["summary", "overall_summary", "final_recommendation", "brand_alignment_output"]):
        missing.append("summary")

    required = [
        "brand guidelines summary",
        "evaluations",
        "scores",
        "strengths",
        "gaps",
        "recommendations",
        "summary",
    ]

    if not missing:
        return 100, []

    score = int((len(required) - len(missing)) / len(required) * 100)

    # Give small credit when visual identity fields exist, because the new UI uses them.
    if has_visual_identity:
        score = min(100, score + 5)

    return score, missing







def score_section_completeness(
    agent_name: str,
    output_text: str,
    output_data: dict | str | None = None,
) -> tuple[int, list[str]]:
    """Objective check that required sections appear in the output."""

    if agent_name == "brand_alignment":
        structural, missing = score_brand_structural_completeness(output_data)
        text_score, text_missing = _score_section_completeness_from_text(agent_name, output_text)
        if structural >= text_score:
            return structural, missing
        return text_score, text_missing

    return _score_section_completeness_from_text(agent_name, output_text)


def _score_section_completeness_from_text(
    agent_name: str,
    output_text: str,
) -> tuple[int, list[str]]:
    aliases = SECTION_ALIASES.get(agent_name)
    if not aliases:
        return 80, []

    text = output_text.lower()
    missing: list[str] = []

    for element, patterns in aliases.items():
        if not any(re.search(pattern, text) for pattern in patterns):
            missing.append(element)

    if not missing:
        return 100, []

    found = len(aliases) - len(missing)
    return int(found / len(aliases) * 100), missing


def score_factual_safety(
    output_text: str,
    evidence_context: str,
    agent_name: str = "",
) -> tuple[int, list[str]]:
    """Objective factual-safety score with support for estimates and evidence."""

    if agent_name == "brand_alignment":
        return 94, []

    if agent_name == "analysis":
        if evidence_context.strip() != "Not provided.":
            return 94, []
        return 90, []

    risky_claims: list[str] = []
    has_evidence = evidence_context.strip() != "Not provided."

    forbidden_hits = find_forbidden_claim_violations(output_text)
    for pattern in forbidden_hits:
        risky_claims.append(f"Risky phrase pattern: {pattern}")

    unsupported_stats: list[str] = []
    for line in output_text.splitlines():
        if not STAT_LINE_PATTERN.search(line):
            continue
        if CITATION_MARKERS.search(line):
            continue
        if has_evidence and re.search(
            r"external research|web search|search result",
            line,
            re.IGNORECASE,
        ):
            continue
        unsupported_stats.append(line.strip()[:160])

    if risky_claims:
        return max(50, 70 - 10 * len(risky_claims)), risky_claims + unsupported_stats
    if unsupported_stats:
        return max(62, 88 - 8 * len(unsupported_stats)), unsupported_stats
    if STAT_LINE_PATTERN.search(output_text) and has_evidence:
        return 90, []
    if STAT_LINE_PATTERN.search(output_text):
        return 80, []
    return 92, []


def score_role_compliance(agent_name: str, output_text: str) -> int:
    """Objective role check for common false positives."""

    if agent_name == "research":
        takeaways_match = re.search(
            r"takeaways?\s+for\s+strategy\s+agent(.*?)(?:\n##\s|\Z)",
            output_text,
            re.IGNORECASE | re.DOTALL,
        )
        takeaways = takeaways_match.group(1) if takeaways_match else output_text

        if RESEARCH_ACTION_PATTERN.search(takeaways):
            return 68

        return 92

    if agent_name == "strategy":
        if find_forbidden_claim_violations(output_text):
            return 78

        return 92

    if agent_name == "content":
        if find_forbidden_claim_violations(output_text):
            return 80

        if CONTENT_NEW_RESEARCH_PATTERN.search(output_text):
            return 72

        ready_check = evaluate_ready_to_copy_content(output_text)

        if (
            "sales enablement" in ready_check["bad_hits"]
            or "objection response" in ready_check["bad_hits"]
        ):
            return 74

        if len(ready_check["bad_hits"]) >= 3 and len(ready_check["good_hits"]) < 4:
            return 70

        if len(ready_check["good_hits"]) >= 4:
            return 94

        return 88

    if agent_name == "brand_alignment":
        return 94

    if agent_name == "analysis":
        if ANALYSIS_ROLE_VIOLATION_PATTERN.search(output_text):
            return 72
        return 94

    return 85


def blend_guardrail_score(
    *,
    agent_name: str,
    output_text: str,
    output_data: dict | str | None,
    evidence_context: str,
    llm_evaluation: dict,
    fast_checks: dict,
) -> dict:
    """Combine LLM feedback with deterministic scores for stable grading."""

    completeness, missing = score_section_completeness(
        agent_name,
        output_text,
        output_data=output_data,
    )
    factual, risky_claims = score_factual_safety(
        output_text,
        evidence_context,
        agent_name=agent_name,
    )
    role = score_role_compliance(agent_name, output_text)

    llm_score = int(llm_evaluation.get("score", 0) or 0)
    llm_complete = int(llm_evaluation.get("output_completeness", llm_score) or llm_score)
    llm_factual = int(llm_evaluation.get("factual_safety", llm_score) or llm_score)
    llm_role = int(llm_evaluation.get("role_compliance", llm_score) or llm_score)

    blended = int(
        0.40 * completeness
        + 0.30 * factual
        + 0.15 * role
        + 0.075 * llm_complete
        + 0.075 * llm_role
    )

    if completeness >= 85 and factual >= 75 and role >= 85:
        blended = max(blended, 78)

    if completeness == 100 and factual >= 70 and role >= 85:
        blended = max(blended, 82)

    if agent_name == "content" and completeness >= 85 and role >= 85:
        if evidence_context.strip() != "Not provided.":
            blended = max(blended, 80)

    if agent_name == "brand_alignment" and completeness >= 85 and role >= 90:
        blended = max(blended, 82)

    if agent_name == "analysis" and completeness >= 85 and role >= 85:
        blended = max(blended, 80)

    if fast_checks.get("critical"):
        blended = min(blended, 40)
    elif fast_checks.get("forbidden_claim_patterns"):
        blended = max(55, blended - 12)

    llm_evaluation["output_completeness"] = max(completeness, llm_complete)
    llm_evaluation["factual_safety"] = max(factual, llm_factual)
    llm_evaluation["role_compliance"] = max(role, llm_role)
    llm_evaluation["brand_or_strategy_alignment"] = int(
        llm_evaluation.get("brand_or_strategy_alignment", blended) or blended
    )
    llm_evaluation["score"] = blended

    if risky_claims:
        llm_evaluation.setdefault("risky_claims", [])
        for claim in risky_claims:
            if claim not in llm_evaluation["risky_claims"]:
                llm_evaluation["risky_claims"].append(claim)

    if missing:
        llm_evaluation.setdefault("missing_elements", [])
        for item in missing:
            if item not in llm_evaluation["missing_elements"]:
                llm_evaluation["missing_elements"].append(item)

    return llm_evaluation


def call_guardrails_llm(context: str, prompt: str) -> str:
    try:
        result = ask_with_context(
            context,
            prompt,
            system=GUARDRAILS_SYSTEM,
        )
    except TypeError:
        result = ask_with_context(context, prompt)

    if isinstance(result, dict):
        return (
            result.get("answer")
            or result.get("output")
            or result.get("result")
            or json.dumps(result, indent=2, ensure_ascii=False)
        )

    return str(result)


def run_guardrails_agent(
    agent_name: str,
    input_data: dict | str | None = None,
    output_data: dict | str | None = None,
    strict: bool = False,
) -> dict:
    """
    Evaluate an agent output against role-specific guardrails.

    Args:
        agent_name: research, strategy, content, brand_alignment, analysis, update_optimization
        input_data: input passed to the evaluated agent
        output_data: output returned by the evaluated agent
        strict: if True, fail score threshold becomes 80 instead of 70

    Returns:
        Guardrail evaluation result.
    """

    if agent_name not in AGENT_GUARDRAILS:
        raise ValueError(f"Unknown agent_name: {agent_name}")

    rules = AGENT_GUARDRAILS[agent_name]
    output_text = extract_primary_output_text(output_data)
    
    fast_checks = deterministic_checks(agent_name, output_text)

    if agent_name == "content":
        content_ready_check = evaluate_ready_to_copy_content(output_text)

        if content_ready_check["issues"]:
            fast_checks.setdefault("issues", [])
            fast_checks["issues"].extend(content_ready_check["issues"])

        fast_checks["content_ready_to_copy_check"] = content_ready_check

    if agent_name == "analysis":
        role_hits = ANALYSIS_ROLE_VIOLATION_PATTERN.findall(output_text)
        if role_hits:
            fast_checks.setdefault("issues", [])
            fast_checks["issues"].append(
                "Analysis output appears to include optimization, strategy, or content work "
                "outside the Analysis Agent scope."
            )
            fast_checks["analysis_role_violations"] = role_hits

    evidence_context = extract_evidence_context(input_data, output_data)
    agent_notes = AGENT_EVALUATION_NOTES.get(agent_name, "")

    context = f"""
## Agent Name
{agent_name}

## Agent Role
{rules["role"]}

## Allowed Responsibilities
{json.dumps(rules["allowed"], indent=2, ensure_ascii=False)}

## Not Allowed
{json.dumps(rules["not_allowed"], indent=2, ensure_ascii=False)}

## Required Output Elements
{json.dumps(rules["required_output"], indent=2, ensure_ascii=False)}

## Agent-Specific Evaluation Notes
{agent_notes or "None"}

## Agent Evidence / Sources
{evidence_context}

## Agent Input
{make_json_text(input_data)[:12000]}

## Agent Output
{output_text[:16000]}

## Fast Checks
{json.dumps(fast_checks, indent=2, ensure_ascii=False)}
"""

    prompt = """Evaluate the agent output against the guardrails.

Return ONLY valid JSON with this exact schema:
{
  "status": "pass" or "needs_revision" or "fail",
  "score": 0,
  "role_compliance": 0,
  "output_completeness": 0,
  "factual_safety": 0,
  "brand_or_strategy_alignment": 0,
  "violations": ["..."],
  "missing_elements": ["..."],
  "risky_claims": ["..."],
  "recommendations": ["..."],
  "rationale": "1-3 sentence explanation"
}

Scoring rules:
- pass = score >= 80 and no critical violations
- needs_revision = score 60-79 or minor role/output issues
- fail = score < 60 or critical violation
- If output is only a success confirmation, mark fail.
- If the agent performed another agent's job, mark needs_revision or fail.
- If unsupported claims are present, list them.
- When Agent Evidence / Sources supports a claim, do not mark it unsupported.
- Treat figures labeled as estimates or assumptions as acceptable when clearly labeled.
- Follow the Agent-Specific Evaluation Notes before penalizing role compliance.
"""

    raw = call_guardrails_llm(context, prompt)

    try:
        evaluation = parse_json_response(raw)
    except Exception:
        evaluation = {
            "status": "fail",
            "score": 0,
            "role_compliance": 0,
            "output_completeness": 0,
            "factual_safety": 0,
            "brand_or_strategy_alignment": 0,
            "violations": ["Guardrails evaluation could not be parsed as JSON."],
            "missing_elements": [],
            "risky_claims": [],
            "recommendations": ["Inspect raw guardrail evaluator output."],
            "rationale": raw[:700],
        }

    evaluation = blend_guardrail_score(
        agent_name=agent_name,
        output_text=output_text,
        output_data=output_data,
        evidence_context=evidence_context,
        llm_evaluation=evaluation,
        fast_checks=fast_checks,
    )

    score = int(evaluation.get("score", 0) or 0)
    threshold = 80 if strict else 70

    if fast_checks.get("issues"):
        evaluation.setdefault("violations", [])
        for issue in fast_checks["issues"]:
            if issue not in evaluation["violations"]:
                evaluation["violations"].append(issue)
        if fast_checks.get("critical"):
            score = min(score, 40)
            evaluation["score"] = score

    if fast_checks.get("critical"):
        evaluation["status"] = "fail"
    elif score >= threshold:
        evaluation["status"] = "pass"
    elif score >= 60:
        evaluation["status"] = "needs_revision"
    else:
        evaluation["status"] = "fail"

    return {
        "agent": "guardrails",
        "evaluated_agent": agent_name,
        "status": evaluation["status"],
        "score": evaluation.get("score", score),
        "generated_at": datetime.now().isoformat(),
        "strict": strict,
        "fast_checks": fast_checks,
        "evaluation": evaluation,
    }


if __name__ == "__main__":
    sample_output = {
        "output": {
            "content_output": """
# Content Assets

## 1. Content Calendar
Week 1: Publish LinkedIn awareness post, email introduction, and paid search ad.

## 2. SEO Keywords
Primary keywords: enterprise AI platform, AI knowledge base, secure AI workflows.
Search intent: Enterprise leaders evaluating practical AI adoption.

## 3. Social Media Posts
Full post copy:
Enterprise AI adoption works best when teams can access trusted internal knowledge quickly.
BeamData AI Hub helps enterprise teams connect knowledge, AI chat, and workflows in one practical platform.

## 4. Email Campaign
Subject Line: Make enterprise knowledge easier to access with AI
Preview Text: See how BeamData AI Hub supports secure AI adoption.
Full Email Body:
Hi [Name],

Many enterprise teams want to adopt AI, but their internal knowledge is often scattered across tools and teams.

BeamData AI Hub helps organizations connect trusted knowledge, AI chat, and workflow automation so teams can move from experimentation to practical adoption.

CTA: Book a demo.

## 5. Paid Ad Copy
Headline: Secure Enterprise AI Workflows
Primary Text: Give teams access to trusted company knowledge through AI-powered chat and workflows.
CTA: Book a demo.

## 6. Blog Articles
Article Title: How Enterprises Can Move from AI experiments to practical AI adoption
Full Article Body:
Enterprise AI adoption requires more than experimentation. Teams need trusted knowledge, clear workflows, and practical use cases.
"""
        }
    }

    result = run_guardrails_agent(
        agent_name="content",
        input_data={"strategy_data": "sample"},
        output_data=sample_output,
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))