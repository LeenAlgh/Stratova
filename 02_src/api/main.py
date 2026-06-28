"""FastAPI backend for Stratova GTM agents."""

import json
import os
import sys
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from orca_orchestrator import run_orca
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENTS_DIR = os.path.join(ROOT_DIR, "agents")
OUTPUT_DIR = os.path.join(AGENTS_DIR, "output")

if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

app = FastAPI(title="Stratova GTM API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_job_status: dict[str, Any] = {
    "orca": "idle",
    "research": "idle",
    "strategy": "idle",
    "content": "idle",
    "brand": "idle",
}


class ClientConfig(BaseModel):
    product: str = ""
    audience: str = ""
    market: str = ""
    goals: str = ""


class GtmQuery(BaseModel):
    product: str = ""
    audience: str = ""
    market: str = ""
    goals: str = ""


class ContentRunOptions(BaseModel):
    client: ClientConfig | None = None
    generate_images: bool = True
    posts_per_platform: int = 3
    blog_count: int = 2
    email_sequence_length: int = 3


def _slug(company_name: str) -> str:
    return company_name.lower().replace(" ", "_")


def _read_text(path: str) -> str:
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"File not found: {os.path.basename(path)}")
    with open(path, encoding="utf-8") as f:
        return f.read()


def _read_json(path: str) -> dict:
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"File not found: {os.path.basename(path)}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)

@app.get("/")
def root():
    return{
        "status": "All agents are active"
    }

@app.get("/agents")
def agents():
    return [
        "Research Agent",
        "Strategy Agent",
        "Content Agent",
        "Brand Alignment",
        "Analysis & Performance"
    ]

@app.get("/health")
def health():
    return {"status": "ok", "jobs": _job_status}


@app.get("/client/default")
def get_default_client():
    from client_query import DEFAULT_GTM_BRIEF

    return DEFAULT_GTM_BRIEF


@app.get("/jobs/status")
def job_status():
    return _job_status


@app.post("/orca/run")
def run_orca_pipeline(query: GtmQuery | None = None, background: bool = False):
    from client_query import build_user_input_from_config, validate_gtm_brief
    from orca_orchestrator import run_orca

    brief = (query or GtmQuery()).model_dump()
    errors = validate_gtm_brief(brief.get("product", ""), brief.get("audience", ""))
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))

    user_input = build_user_input_from_config(brief)

    def _set_agent_status(value: str) -> None:
        _job_status["orca"] = value
        for key in ("research", "strategy", "content", "brand"):
            _job_status[key] = value

    def _task() -> None:
        _set_agent_status("running")
        try:
            run_orca(user_input)
            _set_agent_status("complete")
        except Exception as exc:
            _set_agent_status(f"error: {exc}")

    if background:
        import threading

        threading.Thread(target=_task, daemon=True).start()
        return {"status": "started", "message": "ORCA pipeline running in background"}

    _set_agent_status("running")
    try:
        result = run_orca(user_input)
        _set_agent_status("complete")
        return {"status": "complete", "result": {"run_id": result.get("run_id")}}
    except Exception as exc:
        _set_agent_status(f"error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/reports")
def get_reports(company: str = "Beam Data"):
    slug = _slug(company)
    return {
        "company": company,
        "slug": slug,
        "research": os.path.exists(os.path.join(AGENTS_DIR, f"research_{slug}.json")),
        "strategy": os.path.exists(os.path.join(AGENTS_DIR, f"strategy_{slug}.json")),
        "content": (
            os.path.exists(os.path.join(AGENTS_DIR, f"content_{slug}.json"))
            or os.path.exists(os.path.join(AGENTS_DIR, f"content_{slug}.txt"))
        ),
        "brand": os.path.exists(os.path.join(AGENTS_DIR, f"brand_{slug}.json")),
    }


@app.get("/research/text")
def get_research_text(company: str = "Beam Data"):
    path = os.path.join(AGENTS_DIR, f"research_{_slug(company)}.txt")
    return {"company": company, "content": _read_text(path)}


@app.get("/research/json")
def get_research_json(company: str = "Beam Data"):
    path = os.path.join(AGENTS_DIR, f"research_{_slug(company)}.json")
    return _read_json(path)


@app.post("/research/run")
def run_research(client: ClientConfig | None = None, background: bool = False):
    from agents.research_agent import run_research_agent

    config = (client or ClientConfig()).model_dump()

    def _task():
        _job_status["research"] = "running"
        try:
            run_research_agent(config)
            _job_status["research"] = "complete"
        except Exception as exc:
            _job_status["research"] = f"error: {exc}"

    if background:
        import threading

        threading.Thread(target=_task, daemon=True).start()
        return {"status": "started", "message": "Research agent running in background"}

    _job_status["research"] = "running"
    try:
        result = run_research_agent(config)
        _job_status["research"] = "complete"
        return {"status": "complete", "result": result}
    except Exception as exc:
        _job_status["research"] = f"error: {exc}"
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/strategy/text")
def get_strategy_text(company: str = "Beam Data"):
    path = os.path.join(AGENTS_DIR, f"strategy_{_slug(company)}.txt")
    return {"company": company, "content": _read_text(path)}


@app.get("/strategy/json")
def get_strategy_json(company: str = "Beam Data"):
    path = os.path.join(AGENTS_DIR, f"strategy_{_slug(company)}.json")
    return _read_json(path)


@app.post("/strategy/run")
def run_strategy(client: ClientConfig | None = None, background: bool = False):
    from agents.strategy_agent import run_strategy_agent

    config = (client or ClientConfig()).model_dump()
    slug = _slug(config["company_name"])
    research_path = os.path.join(AGENTS_DIR, f"research_{slug}.json")
    if not os.path.exists(research_path):
        raise HTTPException(
            status_code=400,
            detail="Research output not found. Run the Research Agent first.",
        )

    def _task():
        _job_status["strategy"] = "running"
        try:
            run_strategy_agent(config)
            _job_status["strategy"] = "complete"
        except Exception as exc:
            _job_status["strategy"] = f"error: {exc}"

    if background:
        import threading

        threading.Thread(target=_task, daemon=True).start()
        return {"status": "started", "message": "Strategy agent running in background"}

    _job_status["strategy"] = "running"
    try:
        result = run_strategy_agent(config)
        _job_status["strategy"] = "complete"
        return {"status": "complete", "result": result}
    except Exception as exc:
        _job_status["strategy"] = f"error: {exc}"
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/content/text")
def get_content_text(company: str = "Beam Data"):
    path = os.path.join(AGENTS_DIR, f"content_{_slug(company)}.txt")
    return {"company": company, "content": _read_text(path)}


@app.get("/content/json")
def get_content_json(company: str = "Beam Data"):
    path = os.path.join(AGENTS_DIR, f"content_{_slug(company)}.json")
    return _read_json(path)


@app.post("/content/run")
def run_content(options: ContentRunOptions | None = None, background: bool = False):
    from agents.content_agent import run_content_agent

    opts = options or ContentRunOptions()
    config = (opts.client or ClientConfig()).model_dump()
    slug = _slug(config["company_name"])
    strategy_path = os.path.join(AGENTS_DIR, f"strategy_{slug}.json")
    if not os.path.exists(strategy_path):
        raise HTTPException(
            status_code=400,
            detail="Strategy output not found. Run the Strategy Agent first.",
        )

    def _task():
        _job_status["content"] = "running"
        try:
            run_content_agent(
                config,
                generate_images=opts.generate_images,
                posts_per_platform=opts.posts_per_platform,
                blog_count=opts.blog_count,
                email_sequence_length=opts.email_sequence_length,
            )
            _job_status["content"] = "complete"
        except Exception as exc:
            _job_status["content"] = f"error: {exc}"

    if background:
        import threading

        threading.Thread(target=_task, daemon=True).start()
        return {"status": "started", "message": "Content agent running in background"}

    _job_status["content"] = "running"
    try:
        result = run_content_agent(
            config,
            generate_images=opts.generate_images,
            posts_per_platform=opts.posts_per_platform,
            blog_count=opts.blog_count,
            email_sequence_length=opts.email_sequence_length,
        )
        _job_status["content"] = "complete"
        return {"status": "complete", "result": result}
    except Exception as exc:
        _job_status["content"] = f"error: {exc}"
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/brand/text")
def get_brand_text(company: str = "Beam Data"):
    path = os.path.join(AGENTS_DIR, f"brand_{_slug(company)}.txt")
    return {"company": company, "content": _read_text(path)}


@app.get("/brand/json")
def get_brand_json(company: str = "Beam Data"):
    path = os.path.join(AGENTS_DIR, f"brand_{_slug(company)}.json")
    return _read_json(path)


@app.get("/brand/identity")
def get_brand_identity():
    from knowledge_base.brand_identity import get_visual_system, get_logo_base64

    visual = get_visual_system()
    logo_b64 = get_logo_base64()
    return {"visual_system": visual, "logo_base64": logo_b64}


@app.post("/brand/run")
def run_brand(client: ClientConfig | None = None, background: bool = False):
    from agents.brand_agent import run_brand_agent

    config = (client or ClientConfig()).model_dump()
    slug = _slug(config["company_name"])
    content_json = os.path.join(AGENTS_DIR, f"content_{slug}.json")
    content_txt = os.path.join(AGENTS_DIR, f"content_{slug}.txt")
    if not os.path.exists(content_json) and not os.path.exists(content_txt):
        raise HTTPException(
            status_code=400,
            detail="Content output not found. Run the Content Agent first.",
        )

    def _task():
        _job_status["brand"] = "running"
        try:
            run_brand_agent(config)
            _job_status["brand"] = "complete"
        except Exception as exc:
            _job_status["brand"] = f"error: {exc}"

    if background:
        import threading

        threading.Thread(target=_task, daemon=True).start()
        return {"status": "started", "message": "Brand agent running in background"}

    _job_status["brand"] = "running"
    try:
        result = run_brand_agent(config)
        _job_status["brand"] = "complete"
        return {"status": "complete", "result": result}
    except Exception as exc:
        _job_status["brand"] = f"error: {exc}"
        raise HTTPException(status_code=500, detail=str(exc)) from exc


if os.path.isdir(OUTPUT_DIR):
    app.mount("/content/images", StaticFiles(directory=OUTPUT_DIR), name="content_images")
