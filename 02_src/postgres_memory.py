"""
PostgreSQL Memory Manager for Stratova GTM Multi-Agent System.

Core flow only:
Research -> Strategy -> Content -> Brand Alignment

Purpose:
- LangGraph state = short-term memory during one run.
- PostgreSQL = long-term memory across runs.
- Streamlit UI files remain UI files.
- Memory stores summaries, guardrail scores, tags, and file references.

Install:
    python -m pip install "psycopg[binary]" python-dotenv

.env:
    DATABASE_URL=postgresql://postgres:password@localhost:5432/stratova_memory

OR use:
    POSTGRES_HOST=localhost
    POSTGRES_PORT=5432
    POSTGRES_DB=stratova_memory
    POSTGRES_USER=postgres
    POSTGRES_PASSWORD=your_password
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError as exc:
    raise ImportError(
        "Missing PostgreSQL dependency. Install it with: python -m pip install 'psycopg[binary]'"
    ) from exc


from project_paths import ENV_PATH

ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(ENV_PATH)

CORE_AGENT_NAMES = [
    "research",
    "strategy",
    "content",
    "brand_alignment",
]

DEFAULT_CORE_MEMORY = {
    "company_profile": {},
    "brand_guidance": {},
    "user_preferences": {
        "output_style": "clear, practical, structured",
        "agent_architecture": "research -> strategy -> content -> brand_alignment",
        "file_saving": "UI-only JSON files; pipeline uses LangGraph state",
        "guardrails_mode": "evaluation-only",
    },
    "project_rules": {
        "current_state_over_memory": True,
        "do_not_override_current_user_input": True,
        "memory_is_context_not_source_of_truth": True,
    },
}


# =========================
# Connection
# =========================

def get_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")

    if database_url:
        return database_url

    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "stratova_memory")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "")

    if not password:
        raise ValueError(
            "PostgreSQL password is missing. Set DATABASE_URL or POSTGRES_PASSWORD in .env."
        )

    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


def get_connection():
    return psycopg.connect(get_database_url(), row_factory=dict_row)


# =========================
# JSON helpers
# =========================

def make_json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): make_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [make_json_safe(item) for item in value]
    return str(value)


def as_jsonb(value: Any) -> str:
    return json.dumps(make_json_safe(value), ensure_ascii=False)


def summarize_text(text: str, max_chars: int = 1200) -> str:
    clean = re.sub(r"\s+", " ", text or "").strip()
    if len(clean) <= max_chars:
        return clean
    return clean[:max_chars].rstrip() + "..."


def extract_primary_text(data: Any) -> str:
    """Extract useful text from common agent/UI output structures."""

    if data is None:
        return ""

    if isinstance(data, str):
        return data

    if not isinstance(data, dict):
        return str(data)

    # UI payload shape
    if isinstance(data.get("summary"), str):
        return data["summary"]

    if isinstance(data.get("sections"), list):
        sections_text = []
        for section in data["sections"]:
            if isinstance(section, dict):
                title = section.get("title", "")
                body = section.get("body", "")
                sections_text.append(f"{title}\n{body}")
        if sections_text:
            return "\n\n".join(sections_text)

    output = data.get("output", data)

    if isinstance(output, str):
        return output

    if not isinstance(output, dict):
        return json.dumps(make_json_safe(output), indent=2, ensure_ascii=False)

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

    return json.dumps(make_json_safe(output), indent=2, ensure_ascii=False)


def extract_guardrails(data: Any) -> dict:
    if not isinstance(data, dict):
        return {}

    guardrails = data.get("guardrails")

    if isinstance(guardrails, dict):
        return guardrails

    output = data.get("output")
    if isinstance(output, dict) and isinstance(output.get("guardrails"), dict):
        return output["guardrails"]

    return {}


# =========================
# Schema
# =========================

def init_memory_db() -> None:
    """Create PostgreSQL memory tables."""

    schema = """
    CREATE EXTENSION IF NOT EXISTS pg_trgm;

    CREATE TABLE IF NOT EXISTS memory_core (
        key TEXT PRIMARY KEY,
        value JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS memory_runs (
        run_id TEXT PRIMARY KEY,
        user_input TEXT,
        run_dir TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        completed_at TIMESTAMPTZ
    );

    CREATE TABLE IF NOT EXISTS memory_agent_outputs (
        id BIGSERIAL PRIMARY KEY,
        run_id TEXT NOT NULL REFERENCES memory_runs(run_id) ON DELETE CASCADE,
        agent_name TEXT NOT NULL,
        summary TEXT NOT NULL,
        guardrails_status TEXT,
        guardrails_score INTEGER,
        tags JSONB NOT NULL DEFAULT '[]'::jsonb,
        ui_file_path TEXT,
        metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_memory_agent_outputs_agent_name
    ON memory_agent_outputs(agent_name);

    CREATE INDEX IF NOT EXISTS idx_memory_agent_outputs_run_id
    ON memory_agent_outputs(run_id);

    CREATE INDEX IF NOT EXISTS idx_memory_agent_outputs_created_at
    ON memory_agent_outputs(created_at DESC);
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(schema)
        conn.commit()

    initialize_core_memory()


def initialize_core_memory() -> None:
    for key, value in DEFAULT_CORE_MEMORY.items():
        save_core_memory(key, value)


# =========================
# Core memory
# =========================

def save_core_memory(key: str, value: dict) -> dict:
    init_sql = """
    INSERT INTO memory_core (key, value, updated_at)
    VALUES (%s, %s::jsonb, NOW())
    ON CONFLICT (key)
    DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
    RETURNING key, value, created_at, updated_at;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(init_sql, (key, as_jsonb(value)))
            row = cur.fetchone()
        conn.commit()

    return row


def get_core_memory() -> dict:
    init_memory_db()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT key, value FROM memory_core;")
            rows = cur.fetchall()

    return {row["key"]: row["value"] for row in rows}


# =========================
# Run memory
# =========================

def save_run_record(
    run_id: str,
    user_input: str | None = None,
    run_dir: str | None = None,
    completed: bool = False,
) -> dict:
    sql = """
    INSERT INTO memory_runs (run_id, user_input, run_dir, completed_at)
    VALUES (%s, %s, %s, CASE WHEN %s THEN NOW() ELSE NULL END)
    ON CONFLICT (run_id)
    DO UPDATE SET
        user_input = COALESCE(EXCLUDED.user_input, memory_runs.user_input),
        run_dir = COALESCE(EXCLUDED.run_dir, memory_runs.run_dir),
        completed_at = CASE WHEN %s THEN NOW() ELSE memory_runs.completed_at END
    RETURNING *;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (run_id, user_input, run_dir, completed, completed))
            row = cur.fetchone()
        conn.commit()

    return row


def save_agent_memory(
    run_id: str,
    agent_name: str,
    output_data: dict | str,
    ui_file_path: str | None = None,
    tags: list[str] | None = None,
) -> dict:
    """Save lightweight memory from one core agent output."""

    if agent_name not in CORE_AGENT_NAMES:
        raise ValueError(
            f"Unsupported agent_name for core memory: {agent_name}. Allowed: {CORE_AGENT_NAMES}"
        )

    init_memory_db()
    save_run_record(run_id=run_id)

    primary_text = extract_primary_text(output_data)
    summary = summarize_text(primary_text)
    guardrails = extract_guardrails(output_data)

    evaluation = guardrails.get("evaluation", {}) if isinstance(guardrails, dict) else {}

    guardrails_status = guardrails.get("status") if isinstance(guardrails, dict) else None
    guardrails_score = guardrails.get("score") if isinstance(guardrails, dict) else None

    if guardrails_score is None and isinstance(evaluation, dict):
        guardrails_score = evaluation.get("score")

    metadata = {
        "text_length": len(primary_text),
        "guardrails": guardrails,
    }

    sql = """
    INSERT INTO memory_agent_outputs
    (run_id, agent_name, summary, guardrails_status, guardrails_score, tags, ui_file_path, metadata)
    VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb)
    RETURNING *;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    run_id,
                    agent_name,
                    summary,
                    guardrails_status,
                    guardrails_score,
                    as_jsonb(tags or [agent_name]),
                    ui_file_path,
                    as_jsonb(metadata),
                ),
            )
            row = cur.fetchone()
        conn.commit()

    return row


def save_memory_from_ui_file(ui_file_path: str) -> dict:
    """Save memory from a Streamlit UI JSON file."""

    path = Path(ui_file_path)

    with open(path, "r", encoding="utf-8") as f:
        ui_data = json.load(f)

    run_id = ui_data.get("run_id")
    agent_name = ui_data.get("agent")

    if not run_id or not agent_name:
        raise ValueError("UI file must contain run_id and agent.")

    return save_agent_memory(
        run_id=run_id,
        agent_name=agent_name,
        output_data=ui_data,
        ui_file_path=str(path),
        tags=[agent_name, "ui_memory"],
    )


def save_completed_run_from_state(run_state: dict) -> dict:
    """Save run + core agent memories from final ORCA state."""

    init_memory_db()

    run_id = run_state.get("run_id")
    if not run_id:
        raise ValueError("run_state must contain run_id.")

    save_run_record(
        run_id=run_id,
        user_input=run_state.get("user_input"),
        run_dir=run_state.get("run_dir"),
        completed=True,
    )

    saved = {}

    for agent_name in CORE_AGENT_NAMES:
        data_key = f"{agent_name}_data"
        path_key = f"{agent_name}_path"

        output_data = run_state.get(data_key)

        if output_data:
            saved[agent_name] = save_agent_memory(
                run_id=run_id,
                agent_name=agent_name,
                output_data=output_data,
                ui_file_path=run_state.get(path_key),
                tags=[agent_name, "orca_run"],
            )

    return {
        "run_id": run_id,
        "saved_agents": saved,
    }


# =========================
# Retrieval
# =========================

def retrieve_memory(
    query: str,
    agent_names: list[str] | None = None,
    limit: int = 5,
) -> list[dict]:
    """Retrieve recent relevant memory using simple PostgreSQL text search."""

    init_memory_db()

    if agent_names is None:
        agent_names = CORE_AGENT_NAMES

    search_query = f"%{query}%"

    sql = """
    SELECT *
    FROM memory_agent_outputs
    WHERE agent_name = ANY(%s)
      AND (
        summary ILIKE %s
        OR tags::text ILIKE %s
        OR metadata::text ILIKE %s
      )
    ORDER BY created_at DESC
    LIMIT %s;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (agent_names, search_query, search_query, search_query, limit))
            rows = cur.fetchall()

    return rows


def load_recent_agent_memory(agent_name: str, limit: int = 3) -> list[dict]:
    init_memory_db()

    sql = """
    SELECT *
    FROM memory_agent_outputs
    WHERE agent_name = %s
    ORDER BY created_at DESC
    LIMIT %s;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (agent_name, limit))
            rows = cur.fetchall()

    return rows


def build_memory_context(
    user_input: str,
    agent_name: str | None = None,
    limit: int = 5,
) -> str:
    """
    Build memory context to inject into agent prompts.

    Important:
    Current user input and LangGraph state remain the source of truth.
    Memory is only supporting context.
    """

    core = get_core_memory()
    agent_filter = [agent_name] if agent_name else CORE_AGENT_NAMES
    retrieved = retrieve_memory(user_input, agent_names=agent_filter, limit=limit)

    return f"""
## Long-Term Memory Context

Use this as supporting context only.
Do not override current user input or current LangGraph state.

## Core Memory
{json.dumps(make_json_safe(core), indent=2, ensure_ascii=False)}

## Retrieved Past Agent Memory
{json.dumps(make_json_safe(retrieved), indent=2, ensure_ascii=False)}
"""


if __name__ == "__main__":
    init_memory_db()
    print("PostgreSQL memory tables are ready.")
