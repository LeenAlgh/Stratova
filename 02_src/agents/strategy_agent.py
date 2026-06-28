"""
Strategy Agent — ICP, Personas, Positioning, Messaging, and GTM Strategy.

This version is designed for ORCA/LangGraph:
- It does NOT read research from files.
- It does NOT save output files.
- It receives Research Agent output from LangGraph state.
- ORCA handles all file saving for Streamlit/FastAPI.
"""

import json
import os
import sys
import re
from datetime import datetime

from langchain.tools import tool
from langchain.agents import create_agent

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENTS_DIR = os.path.dirname(os.path.abspath(__file__))

if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from knowledge_base.rag import ask_with_context, llm
from knowledge_base.brand_identity import DEFAULT_BRAND_IDENTITY_PDF, load_brand_identity

from project_paths import KB_DOCS_DIR

BRAND_IDENTITY_PDF = str(KB_DOCS_DIR / DEFAULT_BRAND_IDENTITY_PDF)

STRATEGY_SYSTEM = """You are an expert B2B Go-To-Market Strategy Agent.

You work AFTER the Research Agent in an ORCA/LangGraph workflow.
You receive Research Agent output through LangGraph state.
You do NOT read research files.
You do NOT save output files.
You do NOT create social posts, blogs, ads, or email copy. That belongs to the Content Agent.

Your job is to convert research into a clear, practical, executive-ready GTM strategy.

Brand alignment is mandatory.
Before finalizing the strategy, you must use the official brand identity guidelines.
The strategy must reflect the company’s approved brand voice, positioning, tone, value proposition, and messaging direction.

You must use:

1. Research Agent output as the source of truth for market, competitors, audience, opportunities, and risks.
2. Brand identity guidelines as the source of truth for tone, positioning, voice, messaging style, and brand consistency.

Important brand alignment rules:

* Do not create positioning that conflicts with the brand identity.
* Do not use exaggerated, generic, or unsupported claims.
* Do not describe the company in a way that is not supported by the brand guidelines.
* Messaging must match the brand voice.
* Differentiation must be credible and consistent with the brand.
* Channel recommendations must fit the audience and brand tone.
* GTM strategy must support the brand’s long-term positioning, not just short-term acquisition.
* If research and brand identity conflict, state the conflict clearly and choose the safer brand-aligned recommendation.

You must not invent unsupported facts.
If research is incomplete, state assumptions clearly.
Every recommendation must connect back to either:

* the Research Agent output, or
* the official brand identity guidelines.

Use tools in this recommended order:

1. extract_brand_identity
2. build_icp
3. generate_personas
4. create_positioning_statement
5. generate_messaging_pillars
6. recommend_channels
7. create_gtm_strategy

Use each tool at most once unless the user explicitly asks for more.
After creating the GTM strategy, stop.

Final output must follow this structure:

# GTM Strategy Report

## 1. Executive Summary

Summarize the recommended GTM direction and how it aligns with the brand.

## 2. Brand Alignment Foundation

Explain the key brand identity principles used to shape the strategy:

* Brand voice
* Positioning direction
* Messaging style
* Claims to Avoid: describe categories to avoid (e.g. absolutist promises, instant transformation claims) — do not quote forbidden marketing phrases verbatim in the final report.
* Strategic brand implications

## 3. Strategy Assumptions

List assumptions made because of missing or limited research.

## 4. Ideal Customer Profile

Include firmographics, pain points, buying triggers, decision criteria, and disqualifiers.

## 5. Buyer Personas

Include 2-3 personas with goals, pain points, objections, buying triggers, and preferred channels.

## 6. Positioning

Include:

* Category
* Positioning statement
* Target audience
* Core value proposition
* Differentiation
* Proof points
* Brand alignment notes

## 7. Messaging Pillars

Include 3-5 messaging pillars.
For each pillar include:

* Pillar name
* Core message
* Persona match
* Research support
* Brand alignment note

## 8. Channel Strategy

Recommend channels with:

* Priority
* Rationale
* Target persona
* Content types
* Frequency
* KPI
* Brand fit

## 9. 30-Day GTM Plan

Break the plan into:

* phase 1: Foundation
* phase 2: Activation
* phase 3: Scale

Each phase should include specific actions that fit the brand voice and positioning.

## 10. Metrics

Include key GTM metrics and target indicators.

## 11. Risks and Mitigation

List key risks and how to reduce them.

## 12. Handoff to Content Agent

Give clear instructions for what the Content Agent should create next.
Include:

* brand tone to follow
* messages to emphasize
* claims to avoid
* best channels
* first content priorities

Use these exact section headings in the final report:
## 1. Executive Summary
## 2. Brand Alignment Foundation
## 3. Strategy Assumptions
## 4. Ideal Customer Profile (ICP)
## 5. Buyer Personas
## 6. Positioning
## 7. Messaging Pillars
## 8. Channel Strategy
## 9. 30-Day GTM Plan
## 10. Metrics
## 11. Risks and Mitigation
## 12. Handoff to Content Agent
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

def format_research_for_strategy(research_data: dict | str) -> str:
    """
    Convert Research Agent output into a clean context string for the Strategy Agent.
    """
    if isinstance(research_data, str):
        return research_data

    return json.dumps(
        research_data,
        indent=2,
        ensure_ascii=False
    )

def get_last_content(response) -> str:
    """
    Extract the final text message from a LangChain/LangGraph agent response.
    """
    for message in reversed(response["messages"]):
        if hasattr(message, "content") and message.content:
            return message.content

    return ""


def call_strategy_llm(context: str, task_prompt: str, system: str = STRATEGY_SYSTEM) -> str:
    """
    Safe wrapper for ask_with_context.
    Handles different function signatures and return formats.
    """

    try:
        result = ask_with_context(
            context,
            task_prompt,
            system=system
        )
    except TypeError:
        result = ask_with_context(context, task_prompt)

    if isinstance(result, dict):
        return (
            result.get("answer")
            or result.get("output")
            or result.get("result")
            or json.dumps(result, indent=2, ensure_ascii=False)
        )

    return str(result)


def generate_strategy(context: str, task_prompt: str) -> str:
    """
    Generate strategy output grounded in research context and a task-specific prompt.
    Base LLM helper used by all strategy generation steps.
    """

    return call_strategy_llm(context, task_prompt, system=STRATEGY_SYSTEM)


def extract_brand_guidance() -> dict:
    """
    Extract structured brand guidance from the official brand identity PDF.
    Used internally by the Strategy Agent and passed to the Content Agent.
    """
    identity = load_brand_identity(BRAND_IDENTITY_PDF)

    brand_context = f"""
Source: {identity["doc_id"]}
Pages: {identity["page_count"]}

Brand Identity Document:
{identity["formatted"]}
"""

    prompt = """
Extract the brand guidance needed for GTM strategy and content creation.

Return ONLY valid JSON with this structure:

{
  "source": "",
  "brand_positioning": "",
  "brand_voice": "",
  "tone": "",
  "messaging_style": "",
  "preferred_terms": [],
  "terms_to_avoid": [],
  "claims_to_avoid": [],
  "content_do": [],
  "content_dont": [],
  "visual_style_notes": "",
  "strategy_implications": "",
  "content_implications": ""
}

Rules:
Use only the brand identity document.
Do not invent brand rules.
Focus on guidance that affects strategy, messaging, and content.
Include claims the Content Agent should avoid.
Include preferred language and tone.
"""

    raw = call_strategy_llm(
        brand_context,
        prompt,
        system="You are a brand identity extraction specialist."
    )

    try:
        brand_guidance = parse_json_response(raw)
    except Exception:
        brand_guidance = {
            "source": identity["doc_id"],
            "brand_positioning": "",
            "brand_voice": "",
            "tone": "",
            "messaging_style": "",
            "preferred_terms": [],
            "terms_to_avoid": [],
            "claims_to_avoid": [],
            "content_do": [],
            "content_dont": [],
            "visual_style_notes": "",
            "strategy_implications": "",
            "content_implications": raw,
            "parse_error": "Brand guidance could not be parsed as JSON."
        }

    brand_guidance["source"] = identity["doc_id"]

    return brand_guidance

@tool
def extract_brand_identity() -> str:
    """
    Extract structured brand guidance from the official brand identity PDF
    and return it as formatted JSON for strategy and content alignment.
    """

    brand_guidance = extract_brand_guidance()

    return json.dumps(
        brand_guidance,
        indent=2,
        ensure_ascii=False
    )

@tool
def build_icp(research_context: str) -> str:
    """
    Build a detailed Ideal Customer Profile (firmographics, pain points, buying triggers)
    from Research Agent output.
    """
    prompt = """
Build a detailed Ideal Customer Profile based only on the research context.

Include:
- Firmographics
- Industry fit
- Company size/stage
- Geography
- Technology maturity
- Pain points
- Buying triggers
- Decision criteria
- Disqualifiers

Make the ICP specific and practical for GTM execution.
"""

    return generate_strategy(research_context, prompt)


@tool
def generate_personas(research_context: str, icp: str) -> str:
    """
    Generate 2-3 buyer personas with goals, pain points, objections, and channel 
    preferences using research context and the ICP.
    """
    prompt = f"""
Generate 2-3 detailed buyer personas based on the research context and ICP.

ICP:
{icp}

For each persona include:
- Persona name
- Job title
- Role in buying committee
- Goals
- Pain points
- Objections
- Buying triggers
- Preferred channels
- Message that would resonate
"""

    return generate_strategy(research_context, prompt)


@tool
def create_positioning_statement(research_context: str) -> str:
    """
    Create positioning and differentiation including category, value proposition,
    proof points, and claims to avoid from research context.
    """
    prompt = """
Create a positioning strategy based on the research context.

Include:
- Category
- Positioning statement
- Target audience
- Main value proposition
- Differentiation from competitors
- Proof points from research
- What the company should avoid claiming
"""

    return generate_strategy(research_context, prompt)


@tool
def generate_messaging_pillars(research_context: str, personas: str) -> str:
    """
    Generate 3-5 messaging pillars mapped to personas, pain points, and research-backed proof points.
    """
    prompt = f"""
Generate 3-5 messaging pillars based on the research context and personas.

Personas:
{personas}

For each messaging pillar include:
- Pillar name
- Core message
- Persona match
- Pain point addressed
- Proof points from research
- Best channel for this message
"""

    return generate_strategy(research_context, prompt)


@tool
def recommend_channels(research_context: str, personas: str) -> str:
    """
    Recommend a prioritized GTM channel mix with content types, frequency, funnel stage, and KPIs per channel.
    """
    prompt = f"""
Recommend a prioritized GTM channel mix based on the research context and personas.

Personas:
{personas}

For each channel include:
- Priority rank
- Why this channel fits
- Target persona
- Content types
- Frequency
- Funnel stage
- KPI to track

Do not recommend channels unless they make sense for the audience and market.
"""

    return generate_strategy(research_context, prompt)

@tool
def create_gtm_strategy(
    research_context: str,
    icp: str,
    personas: str,
    positioning: str,
    messaging: str,
    channels: str,
) -> str:
    """
    Create the final GTM Strategy Report combining ICP, personas, positioning, messaging, channels, 30-day plan, metrics, risks, and Content Agent handoff.
    """
    prompt = f"""
Create a complete 30-day GTM strategy using the research context and strategy inputs below.

ICP:
{icp}

Personas:
{personas}

Positioning:
{positioning}

Messaging:
{messaging}

Channels:
{channels}

Use these exact section headings:

# GTM Strategy Report

## 1. Executive Summary
## 2. Brand Alignment Foundation
## 3. Strategy Assumptions
## 4. Ideal Customer Profile (ICP)
## 5. Buyer Personas
## 6. Positioning
## 7. Messaging Pillars
## 8. Channel Strategy
## 9. 30-Day GTM Plan
### Month 1: Foundation
### Month 2: Activation
### Month 3: Scale
## 10. Metrics
## 11. Risks and Mitigation
## 12. Handoff to Content Agent

Rules:
- Ground every recommendation in the research context or brand guidance.
- In "Claims to Avoid", describe categories (e.g. absolutist accuracy promises) — do not quote risky marketing phrases verbatim.
- Do not invent unsupported market statistics.
- Make it concrete, actionable, and executive-ready.
"""

    return generate_strategy(research_context, prompt)

def normalize_strategy_output(strategy_output: str) -> str:
    """
    Normalize section headings in the GTM strategy report to canonical labels
    required by guardrails completeness checks.
    """

    if not strategy_output:
        return strategy_output

    text = strategy_output

    if not re.search(r"ideal\s*customer\s*profile|\bicp\b", text, re.IGNORECASE):
        text = re.sub(
            r"^(#+\s*)?Firmographics\b",
            r"## 4. Ideal Customer Profile (ICP)\n\n### Firmographics",
            text,
            count=1,
            flags=re.IGNORECASE | re.MULTILINE,
        )

    if not re.search(r"channel\s*strategy", text, re.IGNORECASE):
        text = re.sub(
            r"^(#+\s*)?Recommended Channels\b",
            r"## 8. Channel Strategy\n\n### Recommended Channels",
            text,
            count=1,
            flags=re.IGNORECASE | re.MULTILINE,
        )

    return text


strategy_tools = [
    extract_brand_identity,
    build_icp,
    generate_personas,
    create_positioning_statement,
    generate_messaging_pillars,
    recommend_channels,
    create_gtm_strategy,
]


strategy_agent = create_agent(
    model=llm,
    tools=strategy_tools,
    system_prompt=STRATEGY_SYSTEM
)

def run_strategy_agent_from_research(research_data: dict | str) -> dict:
    """
    Run the Strategy Agent using Research Agent output from LangGraph state.

    This version runs strategy tools directly in a fixed order.
    Reason: LangChain agent.invoke may loop through tools without stopping,
    hitting LangGraph's recursion_limit before producing the final GTM report.

    Args:
        research_data: Research Agent output passed from ORCA/LangGraph.

    Returns:
        dict with Strategy Agent output. ORCA is responsible for saving this.
    """

    print("[Strategy Agent] Running from Research Agent output...", flush=True)

    research_context = format_research_for_strategy(research_data)

    print("[Strategy Agent] Extracting brand guidance...", flush=True)
    brand_guidance = extract_brand_guidance()

    strategy_context = f"""
Research Agent Output:
{research_context}

Brand Guidance:
{json.dumps(brand_guidance, indent=2, ensure_ascii=False)}

Important:
The GTM strategy must align with the brand guidance.
Positioning, messaging, channel recommendations, and content handoff must follow the brand voice.
Do not create claims that conflict with the brand guidance.
"""

    print("[Strategy Agent] Building ICP...", flush=True)
    icp = build_icp.invoke({"research_context": strategy_context})

    print("[Strategy Agent] Generating personas...", flush=True)
    personas = generate_personas.invoke({
        "research_context": strategy_context,
        "icp": icp,
    })

    print("[Strategy Agent] Creating positioning...", flush=True)
    positioning = create_positioning_statement.invoke({
        "research_context": strategy_context,
    })

    print("[Strategy Agent] Generating messaging pillars...", flush=True)
    messaging = generate_messaging_pillars.invoke({
        "research_context": strategy_context,
        "personas": personas,
    })

    print("[Strategy Agent] Recommending channels...", flush=True)
    channels = recommend_channels.invoke({
        "research_context": strategy_context,
        "personas": personas,
    })

    print("[Strategy Agent] Creating final GTM strategy...", flush=True)
    strategy_output = create_gtm_strategy.invoke({
        "research_context": strategy_context,
        "icp": icp,
        "personas": personas,
        "positioning": positioning,
        "messaging": messaging,
        "channels": channels,
    })
    strategy_output = normalize_strategy_output(strategy_output)

    results = {
        "agent": "strategy",
        "status": "completed",
        "generated_at": datetime.now().isoformat(),
        "input": {
            "research_data": research_data
        },
        "output": {
            "strategy_output": strategy_output,
            "brand_guidance": brand_guidance,
            "components": {
                "icp": icp,
                "personas": personas,
                "positioning": positioning,
                "messaging_pillars": messaging,
                "channels": channels,
            },
        }
    }

    print("[Strategy Agent] Done.", flush=True)

    return results


if __name__ == "__main__":
    sample_research = {
        "output": {
            "research_output": "Paste Research Agent output here for local testing."
        }
    }

    results = run_strategy_agent_from_research(sample_research)

    print("\nFINAL STRATEGY OUTPUT:\n", flush=True)
    print(results["output"]["strategy_output"], flush=True)