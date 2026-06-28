"""Load agent output files from disk (fallback when API is offline)."""

import json
import os

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENTS_DIR = os.path.join(ROOT_DIR, "agents")


def slug(company_name: str) -> str:
    return company_name.lower().replace(" ", "_")


def agent_path(agent: str, company: str, ext: str = "json") -> str:
    return os.path.join(AGENTS_DIR, f"{agent}_{slug(company)}.{ext}")


def load_local_json(agent: str, company: str) -> dict | None:
    path = agent_path(agent, company, "json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return None


def load_local_text(agent: str, company: str) -> str | None:
    path = agent_path(agent, company, "txt")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return f.read()


def local_reports(company: str) -> dict:
    s = slug(company)
    return {
        "research": os.path.exists(os.path.join(AGENTS_DIR, f"research_{s}.json")),
        "strategy": os.path.exists(os.path.join(AGENTS_DIR, f"strategy_{s}.json")),
        "content": (
            os.path.exists(os.path.join(AGENTS_DIR, f"content_{s}.json"))
            or os.path.exists(os.path.join(AGENTS_DIR, f"content_{s}.txt"))
        ),
        "brand": os.path.exists(os.path.join(AGENTS_DIR, f"brand_{s}.json")),
    }
