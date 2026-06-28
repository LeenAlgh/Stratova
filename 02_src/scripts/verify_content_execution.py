"""Verify content execution + brand handoff (limited blog count for dev)."""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from agents.brand_agent import extract_content_items
from agents.content_agent import run_content_agent_from_strategy

from project_paths import OUTPUT_RUNS_DIR

RUN_DIR = str(OUTPUT_RUNS_DIR / "run_20260622_203052")
STRATEGY_PATH = os.path.join(RUN_DIR, "strategy.json")


def load_strategy_data() -> dict:
    with open(STRATEGY_PATH, encoding="utf-8") as f:
        data = json.load(f)
    # ORCA saves strategy agent return under top-level output
    strategy_data = data.get("output", data)
    if isinstance(strategy_data, dict) and strategy_data.get("output"):
        return strategy_data
    return data


def main() -> None:
    strategy_data = load_strategy_data()
    print("[verify] Running content agent (max_blog_posts=1)...", flush=True)
    content_data = run_content_agent_from_strategy(strategy_data, max_blog_posts=1)

    blog_posts = content_data.get("output", {}).get("blog_posts", {})
    assert blog_posts, "blog_posts must not be empty"
    first_title = next(iter(blog_posts))
    first_body = blog_posts[first_title]
    assert len(first_body) > 200, "blog post body should be substantial"

    items = extract_content_items(content_data)
    assert len(items) > 1, f"expected multiple review items, got {len(items)}"
    blog_items = [i for i in items if i["type"] == "blog"]
    assert blog_items, "expected at least one blog review item"

    out_path = os.path.join(RUN_DIR, "content_verify.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(content_data, f, indent=2, ensure_ascii=False)

    print(f"[verify] OK — blog_posts={len(blog_posts)}, review_items={len(items)}", flush=True)
    print(f"[verify] Saved {out_path}", flush=True)


if __name__ == "__main__":
    main()
