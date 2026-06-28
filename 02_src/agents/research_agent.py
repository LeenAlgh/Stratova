"""
Research Agent — Market Scope, Company Knowledge, Market Research,
Competitor Analysis, and Research Summary.

Combines internal RAG (ChromaDB) with external web scraping and industry news.
Tools mirror agents/text_extraction Beamdata.ipynb, with real external data.
"""

import os
import sys
import json
from datetime import datetime
from langchain_community.utilities import SerpAPIWrapper
from dotenv import load_dotenv
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENTS_DIR = os.path.dirname(os.path.abspath(__file__))

if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from knowledge_base import rag
from knowledge_base.rag import ask_from_kb, ask_with_context, retrieve_context_formatted, ask_llm, ask_general_llm,retrieve_context,llm
from agents.scraper import scrape_competitor, scrape_industry_news, scrape_website

#web search model
load_dotenv()

search = SerpAPIWrapper(
    serpapi_api_key=os.getenv("SERPER_API_KEY")
)

RESEARCH_SYSTEM = """You are an expert Go-To-Market Research Agent.

Your responsibility is to gather research that will later be used by the Strategy Agent.
You do NOT create the final GTM strategy.
You do NOT write final marketing content.

Your research should cover:
- company/product context
- market scope
- market trends
- competitor insights
- audience/customer signals
- marketing channel research
- platform best practices
- opportunities and risks


Tool usage rules:

1. First, identify the research scope:
   - product/service
   - target market
   - target audience

2. Product/service is required.
   If the user does not provide a product/service, ask the user to provide it before continuing.
   

3. Market and audience are optional.
   If market or audience are missing:
   - use retrieve_company_knowledge to infer them if possible
   - if they still cannot be inferred, clearly state your assumptions

4. Use define_market_scope after identifying the product

5. Use retrieve_company_knowledge when you need internal company/product/brand context.

6. Use web_search for external market trends, industry insights, and opportunities.

7. Use analyze_competitors when competitor research is needed.
Competitor analysis must include:

   
at least 4 competitors
competitors in the same market/location
competitors with similar target audience
competitors with comparable company size, stage, or market presence
short description of each competitor
SWOT analysis for each competitor:

     
Strengths
Weaknesses
Opportunities
Threats
clear takeaway for the Strategy Agent

8. Use analyze_marketing_channels to gather research-based channel recommendations.

9. After analyze_marketing_channels returns recommended platforms, call analyze_platform_algorithms once for each recommended platform.

10. Use summarize_research at the end to combine all gathered information into one structured research output.
- Use each tool at most once unless the user explicitly asks for more.
- Do not repeatedly call the same tool.
- Do not loop.
- If a tool returns enough information, move to the next step.
- After summarize_research is used, produce the final answer and stop.


Important:
- Do not invent facts.
- If search results are limited, say that the research may be incomplete.
- Your final output should be useful for the Strategy Agent.
- Cite the source for every market statistic, CAGR, or dollar projection (URL, report name, or "web search result").
- If a figure cannot be verified, label it as an estimate or assumption — never present it as confirmed fact.
- "Key takeaways for Strategy Agent" must be observational research findings only (what the market looks like, what buyers care about).
- Do not write action plans, campaign recommendations, or GTM tactics in research — those belong to the Strategy Agent.




# GTM Research Summary

## 1. Research Scope
- Product/Service:
- Market:
- Audience:
- Assumptions:

## 2. Company/Product Context
Summarize relevant internal company knowledge.

## 3. Market Overview
Summarize market trends and industry context.

## Competitor Insights
For each competitor include:
Name
Short Description
Competitor Type: Direct or Indirect
Why Comparable
Size / Scale Evidence
SWOT Analysis:
Strengths
Weaknesses
Opportunities
Threats
Takeaway for Strategy Agent

## 5. Audience / Customer Signals
Summarize customer needs, pain points, and buying triggers.

## 6. Channel Research
Provide research-based channel recommendations.

## 7. Platform Best Practices
Provide platform-specific insights if relevant.

## 8. Opportunities
List GTM opportunities.

## 9. Risks / Gaps
List risks, missing information, or uncertainty.

## 10. Key Takeaways for Strategy Agent
Give clear points that the Strategy Agent can use later."""


DEFAULT_CLIENT = {
    "company_name": "Beam Data",
    "website_url": "https://beamdata.ai",
    "industry": "AI & Data Consulting",
    "product": "AI Hub — enterprise AI platform for chat, knowledge base, and agentic workflows",
    "market": "North America",
    "audience": "Enterprise data, AI, and IT leaders evaluating AI adoption",
    "stage": "Growth",
    "competitors": ["palantir.com", "databricks.com", "dataiku.com"],
    "goals": "Land 5 enterprise clients in Q3, expand into healthcare vertical",
    "geography": "North America",
}


@tool
def define_market_scope(user_query: str):
    """
    Extract the market scope from the user's natural language GTM request.

    Extract:
    - Product/service
    - Market/location
    - Audience/customer segment
    """

    prompt = f"""
Extract the GTM market scope from the following user request.

User request:
{user_query}

Return ONLY in this format:

Product: ...
Market: ...
Audience: ...
"""


    return ask_general_llm(prompt)

    


@tool
def retrieve_company_knowledge(query: str):
    """
    Retrieve company information from the internal knowledge base.
    """

    context, metadata = retrieve_context(query)

    return context


@tool
def web_search(query: str):
    """
    Search external sources for market trends, industry insights, adoption signals,
    and opportunities. Cite sources when using figures.
    """

    results = search.run(query)
    return (
        "External web search results. Cite these sources when using any figures or claims.\n\n"
        f"{results}"
    )



@tool
def gather_company_knowledge(query: str) -> dict:
    """
    Gather structured company knowledge from the internal KB including overview,
    clients, case studies, differentiators, and source references.
    """
    combined_query = (
        f"{query} company overview mission value proposition services products "
        "clients case studies results differentiators strengths unique capabilities"
    )
    result = ask_from_kb(combined_query)
    return {
        "sections": {"company_knowledge": result["answer"]},
        "sources": result["sources"],
        "formatted": result["answer"],
    }


@tool
def gather_external_data(query: str) -> dict:
    """
    Scrape the company website, competitor sites, and industry news for external
    market and competitive intelligence.
    """
    client = DEFAULT_CLIENT
    website = scrape_website(client["website_url"])
    competitors = {
        domain: scrape_competitor(domain) for domain in client.get("competitors", [])
    }
    news = scrape_industry_news(client["company_name"], client["industry"])
    return {
        "own_website": website,
        "competitors": competitors,
        "industry_news": news,
    }



@tool
def analyze_competitors(user_query: str, market_scope: str = ""):
    """
    Analyze at least 4 relevant competitors with SWOT analysis, comparability notes,
    and takeaways for the Strategy Agent.
    """

    if not market_scope.strip():
        market_scope = define_market_scope.invoke(
            {
                "user_query": user_query
            }
        )

    query = f"""
Find at least 4 competitors for:

{market_scope}

Focus on:
same market/location
similar target audience
comparable company size, stage, or market presence
direct competitors first
indirect competitors only if clearly relevant
avoid very large companies as direct competitors
"""

    search_results = search.run(query)

    prompt = f"""
You are a GTM Competitor Research Analyst.

Market Scope:
{market_scope}

User Query:
{user_query}

Search Results:
{search_results}

Analyze at least 4 relevant competitors.

Rules:
Focus on competitors in the same market or closest relevant market.
Prefer competitors with comparable company size, stage, or market presence.
Do not treat very large companies as direct competitors if the size gap is too large.
If a large company is relevant, label it as an indirect competitor.
If size evidence is unknown, say "Size evidence not found."
Do not invent facts.

Return exactly:

Competitor Analysis
Market Considered
Competitors
For each competitor include:

#### Competitor: [Name]
Website:
Short Description:
Competitor Type: Direct or Indirect
Why Comparable:
Size / Scale Evidence:

##### SWOT Analysis
Strengths:
Weaknesses:
Opportunities:
Threats:

##### Takeaway for Strategy Agent

Overall Competitive Takeaways
Summarize the main patterns for positioning, messaging, and differentiation.
"""

    return ask_general_llm(prompt)

@tool
def summarize_research(research_text: str):
    """
    Summarize all gathered research into a structured GTM research report with
    market scope, insights, opportunities, risks, and Strategy Agent takeaways.
    """
    prompt = f"""
Summarize the following research into a structured GTM research report.

Research:
{research_text}

Use this exact section structure:

## 1. Market Scope
- Product/Service:
- Market:
- Audience:
- Assumptions (if any):

## 2. Company Context
Summarize relevant internal company/product knowledge.

## 3. Market Insights
Summarize market trends and industry context. Cite a source for every statistic or projection.

## 4. Competitor Insights
For each competitor: name, type (direct/indirect), brief description, and research-based takeaway.

## 5. Audience Insights
Summarize customer needs, pain points, and buying triggers.

## 6. Channel Insights
Summarize research-based channel and platform findings.

## 7. Opportunities
List GTM opportunities supported by the research.

## 8. Risks and Gaps
List risks, missing information, or uncertainty.

## 9. Takeaways for Strategy Agent
List 3-5 observational findings the Strategy Agent should know.
Use phrasing like "Research suggests..." or "The market shows..." — not action directives like "Invest in..." or "Launch a campaign...".

Rules:
- Include `(estimate)` or a URL/source for every number, CAGR, or market-size claim.
- Never use vague citations like "source: external research" without a URL or search snippet reference.
- Do not invent facts not present in the research input.
- Do not include a GTM strategy, content plan, or campaign recommendations.
- Section 6 (Channel Insights) should describe which channels the audience uses — not a full marketing plan.
- Section 9 must not recommend campaigns, budgets, or tactics.
"""

    return ask_general_llm(prompt)

@tool
def analyze_marketing_channels(product: str, audience: str):
    """
    Recommend marketing channels for a product and audience with rationale,
    content types, and posting frequency.
    """

    prompt = f"""
    Analyze the market and recommend marketing channels.

    Product:
    {product}

    Audience:
    {audience}

    Include:
    - Recommended Channels
    - Why each channel is suitable
    - Content Type
    - Posting Frequency
    """

    return ask_general_llm(prompt)


@tool
def analyze_platform_algorithms(platform: str):
    """
    Analyze a social platform's algorithm, best content types, engagement factors,
    posting frequency, and growth recommendations.
    """

    prompt = f"""
    Analyze the algorithm of:

    {platform}

    Include:
    - Best Content Types
    - Engagement Factors
    - Posting Frequency
    - Best Times to Post
    - Growth Recommendations
    """

    result = ask_general_llm(prompt)

    return result


research_tools = [
    define_market_scope,
    retrieve_company_knowledge,
    web_search,
    analyze_competitors,
    summarize_research,
    analyze_marketing_channels,
    analyze_platform_algorithms,
    gather_company_knowledge,
    gather_external_data,
]
#create Agent 
research_agent = create_agent(
    model=llm,
    tools=research_tools,
    system_prompt=RESEARCH_SYSTEM
)


#run agent
def _research_fast_mode_enabled() -> bool:
    return os.getenv("RESEARCH_FAST_MODE", "1").lower() in ("1", "true", "yes")


def _parse_scope_field(market_scope: str, field: str) -> str:
    prefix = f"{field}:"
    for line in str(market_scope).splitlines():
        stripped = line.strip()
        if stripped.lower().startswith(prefix.lower()):
            return stripped.split(":", 1)[1].strip()
    return ""


def _tool_content(value) -> str:
    if isinstance(value, dict):
        if isinstance(value.get("formatted"), str):
            return value["formatted"]
        return json.dumps(value, indent=2, ensure_ascii=False)
    return str(value)


def _build_research_bundle(
    *,
    market_scope: str,
    company_knowledge,
    market_search: str,
    competitors: str,
    channels: str,
    platform_insights: str = "",
) -> str:
    sections = [
        f"## Market Scope\n{market_scope}",
        f"## Company Knowledge\n{_tool_content(company_knowledge)}",
        f"## External Market Search\n{market_search}",
        f"## Competitor Analysis\n{competitors}",
        f"## Channel Research\n{channels}",
    ]
    if platform_insights:
        sections.append(f"## Platform Insights\n{platform_insights}")
    return "\n\n".join(sections)

def build_research_evidence(step_outputs: dict) -> dict:
    evidence = {
        "tool_outputs": [],
        "sources": [],
    }

    for tool_name, content in step_outputs.items():
        if tool_name == "sources":
            continue
        evidence["tool_outputs"].append(
            {
                "tool": tool_name,
                "content": _tool_content(content)[:4000],
            }
        )

    company_knowledge = step_outputs.get("company_knowledge")
    if isinstance(company_knowledge, dict):
        sources = company_knowledge.get("sources")
        if isinstance(sources, list):
            evidence["sources"].extend(sources)

    return evidence


#run agent
def run_research_agent_from_input(user_input: str, *, fast: bool | None = None) -> dict:

    use_fast_mode = _research_fast_mode_enabled() if fast is None else fast

    print("[Research Agent] Running from user input...", flush=True)
    print("[Research Agent] Defining market scope...", flush=True)
    market_scope = define_market_scope.invoke({"user_query": user_input})

    print("[Research Agent] Gathering company knowledge...", flush=True)
    company_knowledge = gather_company_knowledge.invoke({"query": user_input})

    product = _parse_scope_field(market_scope, "Product") or user_input
    market = _parse_scope_field(market_scope, "Market")
    audience = _parse_scope_field(market_scope, "Audience")
    web_query = " ".join(
        part for part in [product, market, "AI market trends opportunities competitors"] if part
    )

    print("[Research Agent] Searching external market data...", flush=True)
    market_search = web_search.invoke({"query": web_query})

    print("[Research Agent] Analyzing competitors...", flush=True)
    competitors = analyze_competitors.invoke(
        {
            "user_query": user_input,
            "market_scope": market_scope,
        }
    )

    print("[Research Agent] Analyzing marketing channels...", flush=True)
    channels = analyze_marketing_channels.invoke(
        {
            "product": product,
            "audience": audience or "enterprise buyers",
        }
    )

    platform_insights = ""
    if use_fast_mode:
        print("[Research Agent] Skipping platform deep-dive (fast mode)...", flush=True)
    else:
        print("[Research Agent] Analyzing primary platform (LinkedIn)...", flush=True)
        platform_insights = analyze_platform_algorithms.invoke({"platform": "LinkedIn"})

    research_bundle = _build_research_bundle(
        market_scope=market_scope,
        company_knowledge=company_knowledge,
        market_search=market_search,
        competitors=competitors,
        channels=channels,
        platform_insights=platform_insights,
    )

    print("[Research Agent] Summarizing research...", flush=True)
    final_output = summarize_research.invoke({"research_text": research_bundle})

    research_output = {
        "research_output": final_output
    }

    evidence = build_research_evidence(
        {
            "define_market_scope": market_scope,
            "gather_company_knowledge": company_knowledge,
            "web_search": market_search,
            "analyze_competitors": competitors,
            "analyze_marketing_channels": channels,
            "analyze_platform_algorithms": platform_insights,
            "summarize_research": final_output,
        }
    )

    results = {
        "agent": "research",
        "status": "completed",
        "generated_at": datetime.now().isoformat(),
        "user_input": user_input,
        "output": research_output,
        "evidence": evidence,
        "fast_mode": use_fast_mode,
    }


    print("[Research Agent] Done.", flush=True)

    return results


if __name__ == "__main__":
    USER_INPUT = """
Research the GTM opportunity for BeamData AI Hub.

Product:
Enterprise AI platform for chat, knowledge base, and agentic AI workflows.

Market:
Saudi Arabia.

Audience:
Enterprise data, AI, and IT leaders evaluating AI platforms.
"""

    results = run_research_agent_from_input(
        user_input=USER_INPUT
    )