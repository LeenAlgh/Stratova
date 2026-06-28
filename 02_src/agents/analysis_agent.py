"""
Analysis Agent — Campaign Performance, Metric Computations, Financial Evaluation, 
Efficiency Assessment, and Structured Performance Summary.

Processes campaign datasets to compute full funnel marketing metrics and financial ROI,
generating a data-driven intelligence report for the GTM multi-agent system.
"""

import os
import sys
import json
from typing import Any
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv
from langchain.tools import tool
from langchain.agents import create_agent

# ==========================================
# Path Setup & Environments
# ==========================================
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENTS_DIR = os.path.dirname(os.path.abspath(__file__))

if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from knowledge_base.rag import llm

load_dotenv()

# ==========================================
# System Prompt Configuration
# ==========================================
ANALYSIS_SYSTEM = """You are an expert GTM Analysis Agent in a Multi-Agent System.

Your responsibility is to analyze marketing campaign performance and generate data-driven performance insights.
You do NOT generate optimization recommendations.
You do NOT update GTM strategies.
You do NOT update content plans.
Focus only on empirical campaign analysis and metrics evaluation.

Your final analysis output must strictly adhere to the following 9-point structure:

# GTM Campaign Analysis Report

## 1. Performance Summary
Provide an overall summary of the analyzed campaign.

## 2. CTR Analysis
Analyze user click-through rates and baseline interest.

## 3. Engagement Analysis
Evaluate audience interactions and content resonance.

## 4. Lead Analysis
Assess the volume and patterns of generated leads.

## 5. Conversion Analysis
Evaluate conversion conversion rates and bottom-funnel performance.

## 6. ROI Analysis
Detail the financial return metrics based on computed cost and revenue.

## 7. Strengths
Identify performance areas that exceeded targets or showed top efficiency.

## 8. Weaknesses
Identify drop-offs, low conversion points, or cost inefficiencies.

## 9. Key Insights
Provide objective, data-driven conclusions for the multi-agent orchestration workflow.

Important Rules:
- The report must be data-driven, objective, and based only on available campaign metrics.
- Do not make unsupported or creative assumptions.
"""

# ==========================================
# Tool Definitions
# ==========================================

@tool
def calculate_roi(cost: float, revenue: float) -> str:
    """
    Calculate Return on Investment (ROI) and output a JSON dictionary.
    """
    if cost == 0:
        return json.dumps({"ROI": 0.0})

    roi = ((revenue - cost) / cost) * 100
    return json.dumps({"ROI": round(roi, 2)})


@tool
def analyze_campaign_metrics(campaign_data_json: str) -> str:
    """
    Compute raw marketing indicators (CTR, Engagement Rate, CPL, CPA, Conversion Rates) 
    from a campaign dataset JSON string.
    """
    try:
        data = json.loads(campaign_data_json)
        campaign_df = pd.DataFrame(data if isinstance(data, list) else [data])
        
        total_impressions = int(campaign_df["Impressions"].sum())
        total_reach = int(campaign_df["Reach"].sum())
        total_clicks = int(campaign_df["Clicks"].sum())
        total_engagement = int(campaign_df["Engagement"].sum())
        total_leads = int(campaign_df["Leads"].sum())
        total_conversions = int(campaign_df["Conversions"].sum())

        total_cost = float(campaign_df["Cost"].sum())
        total_revenue = float(campaign_df["Revenue"].sum())

        ctr = ((total_clicks / total_impressions) * 100 if total_impressions > 0 else 0.0)
        engagement_rate = ((total_engagement / total_impressions) * 100 if total_impressions > 0 else 0.0)
        lead_conversion_rate = ((total_leads / total_clicks) * 100 if total_clicks > 0 else 0.0)
        conversion_rate = ((total_conversions / total_leads) * 100 if total_leads > 0 else 0.0)
        
        cpl = (total_cost / total_leads if total_leads > 0 else 0.0)
        cpa = (total_cost / total_conversions if total_conversions > 0 else 0.0)

        # Invoke inner tool
        roi_raw = calculate_roi.invoke({"cost": total_cost, "revenue": total_revenue})
        roi_val = json.loads(roi_raw).get("ROI", 0.0)

        summary_metrics = {
            "total_impressions": total_impressions,
            "total_reach": total_reach,
            "total_clicks": total_clicks,
            "total_engagement": total_engagement,
            "total_leads": total_leads,
            "total_conversions": total_conversions,
            "total_cost": total_cost,
            "total_revenue": total_revenue,
            "ctr_percentage": round(ctr, 2),
            "engagement_rate_percentage": round(engagement_rate, 2),
            "lead_conversion_rate_percentage": round(lead_conversion_rate, 2),
            "conversion_rate_percentage": round(conversion_rate, 2),
            "cpl": round(cpl, 2),
            "cpa": round(cpa, 2),
            "roi_percentage": roi_val
        }
        return json.dumps(summary_metrics, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Failed to compute metrics: {str(e)}"})


@tool
def summarize_performance_insights(computed_metrics_text: str) -> str:
    """
    Format computed analytics and raw metrics into the official structured 9-point report.
    """
    prompt = f"""
Using the computed data metrics below, map them into the official 9-point structured report format.

Computed Metrics Data:
{computed_metrics_text}

Provide exactly this structure:
# GTM Campaign Analysis Report
## 1. Performance Summary
## 2. CTR Analysis
## 3. Engagement Analysis
## 4. Lead Analysis
## 5. Conversion Analysis
## 6. ROI Analysis
## 7. Strengths
## 8. Weaknesses
## 9. Key Insights
"""
    return llm.invoke(prompt).content if hasattr(llm, "invoke") else str(llm(prompt))


analysis_tools = [
    calculate_roi,
    analyze_campaign_metrics,
    summarize_performance_insights
]

# Create Analysis Agent
analysis_agent = create_agent(
    model=llm,
    tools=analysis_tools,
    system_prompt=ANALYSIS_SYSTEM
)

# ==========================================
# Helper Structuring Functions
# ==========================================

def _tool_content(value) -> str:
    if isinstance(value, dict) or isinstance(value, list):
        return json.dumps(value, indent=2, ensure_ascii=False)
    return str(value)


def build_analysis_evidence(step_outputs: dict) -> dict:
    evidence = {
        "tool_outputs": [],
        "sources": [],
    }
    for tool_name, content in step_outputs.items():
        evidence["tool_outputs"].append(
            {
                "tool": tool_name,
                "content": _tool_content(content)[:4000],
            }
        )
    return evidence

# ==========================================
# Main Execution Entry Point
# ==========================================

def run_analysis_agent_from_input(campaign_data: Any) -> dict:
    print("[Analysis Agent] Running from campaign dataset input...", flush=True)
    
    # Standardize data structure to string/JSON format
    import json
    if isinstance(campaign_data, pd.DataFrame):
        campaign_json = campaign_data.to_json(orient="records")
    elif isinstance(campaign_data, (dict, list)):
        campaign_json = json.dumps(campaign_data)
    else:
        campaign_json = str(campaign_data)

    print("[Analysis Agent] Executing campaign metrics analysis tool...", flush=True)
    computed_metrics = analyze_campaign_metrics.invoke({"campaign_data_json": campaign_json})

    print("[Analysis Agent] Running deep financial calculations (ROI)...", flush=True)
    try:
        metrics_dict = json.loads(computed_metrics)
        cost_val = metrics_dict.get("total_cost", 0.0)
        rev_val = metrics_dict.get("total_revenue", 0.0)
    except:
        cost_val, rev_val = 0.0, 0.0
        
    roi_raw = calculate_roi.invoke({"cost": cost_val, "revenue": rev_val})

    print("[Analysis Agent] Building structured intelligence report...", flush=True)
    final_report = summarize_performance_insights.invoke({"computed_metrics_text": computed_metrics})

    analysis_output = {
        "analysis_output": final_report
    }

    evidence = build_analysis_evidence(
        {
            "analyze_campaign_metrics": computed_metrics,
            "calculate_roi": roi_raw,
            "summarize_performance_insights": final_report,
        }
    )

    results = {
        "agent": "analysis",
        "status": "completed",
        "generated_at": datetime.now().isoformat(),
        "input": {"campaign_data_summary": "Processed structured pipeline dataset"},
        "output": analysis_output,
        "evidence": evidence,
    }

    print("[Analysis Agent] Done.", flush=True)
    return results

def run_analysis_agent():
    """
    Compatibility wrapper for ORCA.
    """

    SAMPLE_CAMPAIGN_DATA = [
        {
            "Impressions": 150000,
            "Reach": 120000,
            "Clicks": 3800,
            "Engagement": 7500,
            "Leads": 450,
            "Conversions": 90,
            "Cost": 2500.0,
            "Revenue": 8500.0
        }
    ]

    return run_analysis_agent_from_input(
        campaign_data=SAMPLE_CAMPAIGN_DATA
    )

if __name__ == "__main__":
    # Sample Mock Campaign Performance Dataset
    SAMPLE_CAMPAIGN_DATA = [
        {
            "Impressions": 150000, 
            "Reach": 120000, 
            "Clicks": 3800, 
            "Engagement": 7500, 
            "Leads": 450, 
            "Conversions": 90, 
            "Cost": 2500.0, 
            "Revenue": 8500.0
        }
    ]

    results = run_analysis_agent_from_input(
        campaign_data=SAMPLE_CAMPAIGN_DATA
    )

    print("\n" + "="*50)
    print("FINAL AGENT OUTPUT REPORT:")
    print("="*50 + "\n")
    print(results["output"]["analysis_output"])