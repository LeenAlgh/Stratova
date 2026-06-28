"""
ORCA Orchestrator — Full GTM Multi-Agent Workflow

Flow:
User Input
  -> Research Agent
  -> Strategy Agent
  -> Content Agent
  -> Brand Alignment Agent
  -> Analysis Agent

LangGraph passes data through state.
ORCA saves only UI-optimized JSON files for Streamlit/FastAPI display.
The pipeline itself uses LangGraph state, not saved files.

Expected agent functions:
- agents.research_agent.run_research_agent_from_input(user_input: str) -> dict
- agents.strategy_agent.run_strategy_agent_from_research(research_data: dict | str) -> dict
- agents.content_agent.run_content_agent_from_strategy(strategy_data: dict | str) -> dict
- agents.brand_agent.run_brand_agent_from_content(content_data: dict | str, strategy_data: dict | None = None) -> dict
- agents.analysis_agent.run_analysis_agent_from_input(campaign_data: Any) -> dict
"""

import json
import re
import os
import sys
from pathlib import Path
from datetime import datetime
import memory_system
from typing import TypedDict, Optional, Any

from langgraph.graph import StateGraph, END


# =========================
# Path setup
# =========================

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


# =========================
# Import agents
# =========================

import agents.research_agent as research_agent_module
import agents.strategy_agent as strategy_agent_module
import agents.content_agent as content_agent_module
import agents.brand_agent as brand_agent_module
import agents.analysis_agent as analysis_agent_module
import agents.guardrails_agent as guardrails_agent_module


# =========================
# ORCA State
# =========================

class OrcaState(TypedDict, total=False):
    user_input: str
    guardrails_results: dict

    run_id: str
    run_dir: str

    research_data: dict
    research_path: str

    strategy_data: dict
    strategy_path: str

    content_data: dict
    content_path: str

    brand_alignment_data: dict
    brand_alignment_path: str

    analysis_data: dict
    analysis_path: str

    final_output: dict
    final_output_path: str


# =========================
# Output helpers
# =========================

from project_paths import OUTPUT_RUNS_DIR

OUTPUT_ROOT = OUTPUT_RUNS_DIR


def create_run_id() -> str:
    return "run_" + datetime.now().strftime("%Y%m%d_%H%M%S")


def make_json_safe(value: Any) -> Any:
    """
    Convert values into JSON-safe data.
    LangChain messages and other objects may not be serializable by default.
    """

    if value is None:
        return None

    if isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, dict):
        return {str(k): make_json_safe(v) for k, v in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [make_json_safe(item) for item in value]

    return str(value)


def get_run_dir(run_id: str) -> Path:
    run_dir = OUTPUT_ROOT / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def write_json_file(file_path: Path, payload: dict) -> str:
    """Write JSON using UTF-8 and compact-safe serialization."""

    file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    return str(file_path)


def extract_nested_text(data: Any, keys: list[str]) -> str:
    """Try common nested keys and return the first matching text."""

    current = data

    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
        else:
            return ""

    if isinstance(current, str):
        return current

    if current is None:
        return ""

    return make_json_safe(current).__str__()


def get_primary_text(agent_name: str, output_data: dict) -> str:
    """Extract the main text output for Streamlit display."""

    if not isinstance(output_data, dict):
        return str(output_data)

    candidates = {
        "research": [
            ["output", "research_output"],
            ["research_output"],
        ],
        "strategy": [
            ["output", "strategy_output"],
            ["strategy_output"],
        ],
        "content": [
            ["output", "content_output"],
            ["content_output"],
        ],
        "brand_alignment": [
            ["output", "brand_alignment_output"],
            ["brand_alignment_output"],
            ["output", "summary", "executive_summary"],
            ["summary", "executive_summary"],
        ],
        "analysis": [
            ["output", "analysis_output"],
            ["analysis_output"],
            ["output", "analysis_report"],
            ["analysis_report"],
        ],
        "update_optimization": [
            ["output", "update_optimization_output"],
            ["update_optimization_output"],
        ],
        "final_output": [
            ["output"],
        ],
    }

    for path in candidates.get(agent_name, []):
        text = extract_nested_text(output_data, path)
        if text:
            return text

    return json.dumps(make_json_safe(output_data), indent=2, ensure_ascii=False)


def summarize_text_for_ui(text: str, max_chars: int = 700) -> str:
    """Create a lightweight preview for cards/lists."""

    clean = re.sub(r"\s+", " ", text or "").strip()

    if len(clean) <= max_chars:
        return clean

    return clean[:max_chars].rstrip() + "..."


def split_markdown_sections(text: str) -> list[dict]:
    """Split markdown-like output into sections for Streamlit tabs/expanders."""

    if not text:
        return []

    lines = text.splitlines()
    sections = []
    current_title = "Overview"
    current_lines = []

    heading_pattern = re.compile(r"^(#{1,3})\s+(.+?)\s*$")

    for line in lines:
        match = heading_pattern.match(line)

        if match:
            if current_lines:
                body = "\n".join(current_lines).strip()
                if body:
                    sections.append(
                        {
                            "title": current_title,
                            "body": body,
                        }
                    )

            current_title = match.group(2).strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_lines:
        body = "\n".join(current_lines).strip()
        if body:
            sections.append(
                {
                    "title": current_title,
                    "body": body,
                }
            )

    if not sections:
        sections.append(
            {
                "title": "Overview",
                "body": text,
            }
        )

    return sections


def extract_ui_metrics(agent_name: str, output_data: dict) -> dict:
    """Extract quick metrics for Streamlit cards."""

    if not isinstance(output_data, dict):
        return {}

    output = output_data.get("output", output_data)

    if agent_name == "brand_alignment":
        summary = output.get("summary", {}) if isinstance(output, dict) else {}
        return {
            "overall_score": summary.get("overall_score"),
            "high_count": summary.get("high_count"),
            "low_count": summary.get("low_count"),
            "total_items": summary.get("total_items"),
        }

    if agent_name == "analysis":
        calculated = output.get("calculated_metrics", {}) if isinstance(output, dict) else {}
        metrics = calculated.get("metrics", {}) if isinstance(calculated, dict) else {}
        return {
            "ctr_percent": metrics.get("ctr_percent"),
            "conversion_rate_percent": metrics.get("conversion_rate_percent"),
            "roi_percent": metrics.get("roi_percent"),
            "leads": metrics.get("leads"),
            "conversions": metrics.get("conversions"),
        }

    return {}




def extract_ui_guardrails(output_data: dict) -> dict:
    """Extract lightweight guardrail result for Streamlit cards."""

    if not isinstance(output_data, dict):
        return {}

    guardrails = output_data.get("guardrails")

    if not isinstance(guardrails, dict):
        return {}

    evaluation = guardrails.get("evaluation", {})

    return {
        "status": guardrails.get("status"),
        "score": guardrails.get("score"),
        "evaluated_agent": guardrails.get("evaluated_agent"),
        "violations": evaluation.get("violations", []),
        "recommendations": evaluation.get("recommendations", []),
        "rationale": evaluation.get("rationale"),
    }


def build_agent_ui_payload(
    run_id: str,
    agent_name: str,
    full_file_path: str,
    output_data: dict,
    status: str,
) -> dict:
    """Build lightweight Streamlit-ready payload for one agent."""

    primary_text = get_primary_text(agent_name, output_data)

    return {
        "run_id": run_id,
        "agent": agent_name,
        "status": status,
        "generated_at": datetime.now().isoformat(),
        "full_file_path": full_file_path,
        "summary": summarize_text_for_ui(primary_text),
        "sections": split_markdown_sections(primary_text),
        "metrics": extract_ui_metrics(agent_name, output_data),
        "guardrails": extract_ui_guardrails(output_data),
    }


def save_latest_run(run_id: str, run_dir: str) -> None:
    """Save quick pointer so Streamlit can load the newest run immediately."""

    latest_path = OUTPUT_ROOT.parent / "latest_run.json"

    payload = {
        "run_id": run_id,
        "run_dir": run_dir,
        "updated_at": datetime.now().isoformat(),
        "manifest_path": str(Path(run_dir) / "manifest.json"),
        "ui_index_path": str(Path(run_dir) / "ui_index.json"),
    }

    write_json_file(latest_path, payload)


def update_manifest(
    run_id: str,
    agent_name: str,
    file_path: str,
    ui_file_path: str | None = None,
    status: str = "completed",
) -> None:
    """
    Update manifest.json so Streamlit/FastAPI can discover available outputs.
    """

    run_dir = get_run_dir(run_id)
    manifest_path = run_dir / "manifest.json"

    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    else:
        manifest = {
            "run_id": run_id,
            "created_at": datetime.now().isoformat(),
            "status": "running",
            "files": {},
            "ui_files": {},
            "agents": {},
        }

    manifest.setdefault("files", {})[agent_name] = file_path

    if ui_file_path:
        manifest.setdefault("ui_files", {})[agent_name] = ui_file_path

    manifest.setdefault("agents", {})[agent_name] = {
        "status": status,
        "updated_at": datetime.now().isoformat(),
        "full_file_path": file_path,
        "ui_file_path": ui_file_path,
    }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    save_latest_run(run_id, str(run_dir))


def update_ui_index(
    run_id: str,
    agent_name: str,
    ui_payload: dict,
) -> str:
    """Update a lightweight UI index file for Streamlit fast loading."""

    run_dir = get_run_dir(run_id)
    ui_index_path = run_dir / "ui_index.json"

    if ui_index_path.exists():
        with open(ui_index_path, "r", encoding="utf-8") as f:
            ui_index = json.load(f)
    else:
        ui_index = {
            "run_id": run_id,
            "updated_at": datetime.now().isoformat(),
            "agents": {},
            "agent_order": [],
        }

    if agent_name not in ui_index["agent_order"]:
        ui_index["agent_order"].append(agent_name)

    ui_index["agents"][agent_name] = {
        "status": ui_payload.get("status"),
        "summary": ui_payload.get("summary"),
        "metrics": ui_payload.get("metrics"),
        "ui_file_path": str(run_dir / f"{agent_name}.ui.json"),
        "full_file_path": ui_payload.get("full_file_path"),
        "section_count": len(ui_payload.get("sections", [])),
        "updated_at": datetime.now().isoformat(),
    }

    ui_index["updated_at"] = datetime.now().isoformat()

    write_json_file(ui_index_path, ui_index)

    return str(ui_index_path)


def save_agent_output(
    run_id: str,
    agent_name: str,
    input_data: dict,
    output_data: dict,
    status: str = "completed",
) -> str:
    """
    Save only the Streamlit UI version of one agent's output.

    Pipeline data is already passed through LangGraph state.
    Files are only for UI, so we do NOT save full raw agent JSON here.

    UI JSON:
    outputs/runs/<run_id>/<agent_name>.ui.json
    """

    run_dir = get_run_dir(run_id)
    ui_file_path = run_dir / f"{agent_name}.ui.json"

    ui_payload = build_agent_ui_payload(
        run_id=run_id,
        agent_name=agent_name,
        full_file_path=str(ui_file_path),
        output_data=output_data,
        status=status,
    )

    ui_payload["file_type"] = "ui_only"
    ui_payload["input_summary"] = summarize_text_for_ui(
        json.dumps(make_json_safe(input_data), ensure_ascii=False),
        max_chars=500,
    )

    write_json_file(ui_file_path, ui_payload)

    update_ui_index(
        run_id=run_id,
        agent_name=agent_name,
        ui_payload=ui_payload,
    )

    update_manifest(
        run_id=run_id,
        agent_name=agent_name,
        file_path=str(ui_file_path),
        ui_file_path=str(ui_file_path),
        status=status,
    )

    return str(ui_file_path)


def save_final_output(run_id: str, final_output: dict) -> str:
    """
    Save only the final Streamlit UI output.
    """

    run_dir = get_run_dir(run_id)
    ui_file_path = run_dir / "final_output.ui.json"

    ui_payload = build_agent_ui_payload(
        run_id=run_id,
        agent_name="final_output",
        full_file_path=str(ui_file_path),
        output_data=final_output,
        status="completed",
    )

    ui_payload["file_type"] = "ui_only"

    write_json_file(ui_file_path, ui_payload)

    update_ui_index(
        run_id=run_id,
        agent_name="final_output",
        ui_payload=ui_payload,
    )

    update_manifest(
        run_id=run_id,
        agent_name="final_output",
        file_path=str(ui_file_path),
        ui_file_path=str(ui_file_path),
        status="completed",
    )

def mark_run_completed(run_id: str) -> None:
    """
    Mark the ORCA run as completed inside manifest.json.
    """

    run_dir = get_run_dir(run_id)
    manifest_path = run_dir / "manifest.json"

    if not manifest_path.exists():
        return

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    manifest["status"] = "completed"
    manifest["completed_at"] = datetime.now().isoformat()

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)


def _content_max_blog_posts() -> int | None:
    """Limit generated blog posts during ORCA runs. Default 2 for faster runs."""
    raw = os.getenv("CONTENT_MAX_BLOG_POSTS", "2").strip()
    if not raw or raw.lower() in ("0", "none", "all"):
        return None
    try:
        value = int(raw)
    except ValueError:
        return 2
    return value if value > 0 else None


# =========================
# Guardrails helper
# =========================

def apply_guardrails(
    state: OrcaState,
    agent_name: str,
    input_data: dict,
    output_data: dict,
) -> tuple[dict, dict]:
    """
    Evaluate an agent output and attach guardrail results to the output data.
    This does NOT block ORCA yet. It only evaluates and stores the result.
    """

    print(f"[ORCA] Running Guardrails for {agent_name}...", flush=True)

    guardrail_result = guardrails_agent_module.run_guardrails_agent(
        agent_name=agent_name,
        input_data=input_data,
        output_data=output_data,
    )

    if isinstance(output_data, dict):
        output_data["guardrails"] = guardrail_result

    guardrails_results = dict(state.get("guardrails_results") or {})
    guardrails_results[agent_name] = guardrail_result

    print(
        f"[ORCA] Guardrails {agent_name}: {guardrail_result.get('status')} "
        f"({guardrail_result.get('score')}/100)",
        flush=True,
    )

    return output_data, guardrails_results


# =========================
# LangGraph Nodes
# =========================

def research_node(state: OrcaState) -> OrcaState:
    print("[ORCA] Running Research Agent...", flush=True)

    run_id = state.get("run_id") or create_run_id()
    user_input = state["user_input"]

    research_data = research_agent_module.run_research_agent_from_input(
        user_input=user_input
    )

    research_input = {
        "user_input": user_input,
    }

    research_data, guardrails_results = apply_guardrails(
        state=state,
        agent_name="research",
        input_data=research_input,
        output_data=research_data,
    )

    research_path = save_agent_output(
        run_id=run_id,
        agent_name="research",
        input_data=research_input,
        output_data=research_data,
    )

    print(f"[ORCA] Research saved: {research_path}", flush=True)

    return {
        "run_id": run_id,
        "run_dir": str(get_run_dir(run_id)),
        "research_data": research_data,
        "research_path": research_path,
        "guardrails_results": guardrails_results,
    }


def strategy_node(state: OrcaState) -> OrcaState:
    print("[ORCA] Running Strategy Agent...", flush=True)

    run_id = state["run_id"]
    research_data = state["research_data"]

    strategy_data = strategy_agent_module.run_strategy_agent_from_research(
        research_data=research_data
    )

    strategy_input = {
        "research_path": state.get("research_path"),
        "research_data": research_data,
    }

    strategy_data, guardrails_results = apply_guardrails(
        state=state,
        agent_name="strategy",
        input_data=strategy_input,
        output_data=strategy_data,
    )

    strategy_path = save_agent_output(
        run_id=run_id,
        agent_name="strategy",
        input_data=strategy_input,
        output_data=strategy_data,
    )

    print(f"[ORCA] Strategy saved: {strategy_path}", flush=True)

    return {
        "strategy_data": strategy_data,
        "strategy_path": strategy_path,
        "guardrails_results": guardrails_results,
    }


def content_node(state: OrcaState) -> OrcaState:
    print("[ORCA] Running Content Agent...", flush=True)

    run_id = state["run_id"]
    strategy_data = state["strategy_data"]
    memory_context = state.get("memory_context", "")

    content_data = content_agent_module.run_content_agent_from_strategy(
        strategy_data=strategy_data,
        memory_context=memory_context,
        max_blog_posts=_content_max_blog_posts(),
    )

    content_input = {
        "strategy_path": state.get("strategy_path"),
        "strategy_data": strategy_data,
    }

    content_data, guardrails_results = apply_guardrails(
        state=state,
        agent_name="content",
        input_data=content_input,
        output_data=content_data,
    )

    content_path = save_agent_output(
        run_id=run_id,
        agent_name="content",
        input_data=content_input,
        output_data=content_data,
    )

    print(f"[ORCA] Content saved: {content_path}", flush=True)

    return {
        "content_data": content_data,
        "content_path": content_path,
        "guardrails_results": guardrails_results,
    }


def brand_alignment_node(state: OrcaState) -> OrcaState:
    print("[ORCA] Running Brand Alignment Agent...", flush=True)

    run_id = state["run_id"]
    content_data = state["content_data"]
    strategy_data = state.get("strategy_data")

    brand_alignment_data = brand_agent_module.run_brand_agent_from_content(
        content_data=content_data,
        strategy_data=strategy_data,
    )

    brand_alignment_input = {
        "content_path": state.get("content_path"),
        "content_data": content_data,
        "strategy_data": strategy_data,
    }

    brand_alignment_data, guardrails_results = apply_guardrails(
        state=state,
        agent_name="brand_alignment",
        input_data=brand_alignment_input,
        output_data=brand_alignment_data,
    )

    brand_alignment_path = save_agent_output(
        run_id=run_id,
        agent_name="brand_alignment",
        input_data=brand_alignment_input,
        output_data=brand_alignment_data,
    )

    print(f"[ORCA] Brand alignment saved: {brand_alignment_path}", flush=True)

    return {
        "brand_alignment_data": brand_alignment_data,
        "brand_alignment_path": brand_alignment_path,
        "guardrails_results": guardrails_results,
    }


def analysis_node(state: OrcaState) -> OrcaState:
    print("[ORCA] Running Analysis Agent...", flush=True)

    run_id = state["run_id"]

    analysis_data = analysis_agent_module.run_analysis_agent()

    analysis_input = {
        "campaign_dataset": "Campaign_Performance",
        "feedback_dataset": "Customer_Feedback",
    }

    analysis_data, guardrails_results = apply_guardrails(
        state=state,
        agent_name="analysis",
        input_data=analysis_input,
        output_data=analysis_data,
    )

    analysis_path = save_agent_output(
        run_id=run_id,
        agent_name="analysis",
        input_data=analysis_input,
        output_data=analysis_data,
    )

    print(f"[ORCA] Analysis saved: {analysis_path}", flush=True)

    return {
        "analysis_data": analysis_data,
        "analysis_path": analysis_path,
        "guardrails_results": guardrails_results,
    }


def final_output_node(state: OrcaState) -> OrcaState:
    print("[ORCA] Creating final output...", flush=True)

    run_id = state["run_id"]

    final_output = {
        "run_id": run_id,
        "research": state.get("research_data"),
        "strategy": state.get("strategy_data"),
        "content": state.get("content_data"),
        "brand_alignment": state.get("brand_alignment_data"),
        "analysis": state.get("analysis_data"),
        "guardrails": state.get("guardrails_results"),
        "files": {
            "research": state.get("research_path"),
            "strategy": state.get("strategy_path"),
            "content": state.get("content_path"),
            "brand_alignment": state.get("brand_alignment_path"),
            "analysis": state.get("analysis_path"),
        },
    }

    final_output_path = save_final_output(
        run_id=run_id,
        final_output=final_output,
    )

    print(f"[ORCA] Final output saved: {final_output_path}", flush=True)

    return {
        "final_output": final_output,
        "final_output_path": final_output_path,
    }


# =========================
# Build LangGraph
# =========================

orca_graph = StateGraph(OrcaState)

orca_graph.add_node("research", research_node)
orca_graph.add_node("strategy", strategy_node)
orca_graph.add_node("content", content_node)
orca_graph.add_node("brand_alignment", brand_alignment_node)
orca_graph.add_node("analysis", analysis_node)
orca_graph.add_node("final_output", final_output_node)

orca_graph.set_entry_point("research")

orca_graph.add_edge("research", "strategy")
orca_graph.add_edge("strategy", "content")
orca_graph.add_edge("content", "brand_alignment")
orca_graph.add_edge("brand_alignment", "analysis")
orca_graph.add_edge("analysis", "final_output")
orca_graph.add_edge("final_output", END)

orca_app = orca_graph.compile()


# =========================
# Public run function
# =========================

def run_orca(
    user_input: str,
    run_id: Optional[str] = None,
) -> dict:
    """
    Run the full ORCA workflow.

    Args:
        user_input: Natural language GTM request.
        run_id: Optional existing run_id. If omitted, ORCA creates a new one.

    Returns:
        LangGraph final state including output file paths.
    """

    memory_state = memory_system.prepare_initial_memory_state(user_input)

    initial_state = {
        "user_input": user_input,
        "guardrails_results": {},
        **memory_state,
    }

    if run_id:
        initial_state["run_id"] = run_id

    result = orca_app.invoke(
        initial_state,
        config={"recursion_limit": 120},
    )
    memory_system.save_long_term_memory_from_state(result)

    return result


# =========================
# Local test
# =========================

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

    result = run_orca(USER_INPUT)

    print("\n==============================")
    print("ORCA RUN COMPLETE")
    print("==============================\n")

    print("Run ID:", result.get("run_id"))
    print("Run directory:", result.get("run_dir"))
    print("Final UI output:", result.get("final_output_path"))

    print("\nSaved files:")
    print("Research:", result.get("research_path"))
    print("Strategy:", result.get("strategy_path"))
    print("Content:", result.get("content_path"))
    print("Brand Alignment:", result.get("brand_alignment_path"))
    print("Analysis:", result.get("analysis_path"))