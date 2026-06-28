"""Markdown parsing helpers for UI key findings."""

from __future__ import annotations

import re


def extract_first_heading(text: str, fallback: str = "") -> str:
    if not text:
        return fallback
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#"):
            return line.lstrip("#").strip()
    return fallback


def extract_first_paragraph(text: str, max_len: int = 500) -> str:
    if not text:
        return ""
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    for block in blocks:
        if block.startswith("#"):
            continue
        cleaned = re.sub(r"^#+\s*", "", block)
        cleaned = re.sub(r"\*\*", "", cleaned)
        if len(cleaned) > 20:
            return cleaned[:max_len] + ("…" if len(cleaned) > max_len else "")
    return blocks[0][:max_len] if blocks else ""


def extract_key_findings(text: str, limit: int = 6) -> list[dict[str, str]]:
    """Extract bullet or #### headings as finding cards."""
    if not text:
        return []

    findings: list[dict[str, str]] = []
    seen: set[str] = set()

    for match in re.finditer(r"^####\s+(.+)$", text, re.MULTILINE):
        title = match.group(1).strip()
        title = re.sub(r"\*\*", "", title)
        if title.lower() in seen:
            continue
        start = match.end()
        next_match = re.search(r"^####\s+", text[start:], re.MULTILINE)
        end = start + next_match.start() if next_match else min(start + 300, len(text))
        body = text[start:end].strip()
        body = re.sub(r"^[-*]\s+", "", body.split("\n")[0] if body else "")
        findings.append({"title": title, "body": body[:200]})
        seen.add(title.lower())
        if len(findings) >= limit:
            return findings

    for match in re.finditer(r"^\d+\.\s+\*\*(.+?)\*\*[:\s]*(.*)$", text, re.MULTILINE):
        title = match.group(1).strip()
        body = match.group(2).strip()
        if title.lower() in seen:
            continue
        findings.append({"title": title, "body": body[:200]})
        seen.add(title.lower())
        if len(findings) >= limit:
            return findings

    for match in re.finditer(r"^[-*]\s+\*\*(.+?)\*\*[:\s]*(.*)$", text, re.MULTILINE):
        title = match.group(1).strip()
        body = match.group(2).strip()
        if title.lower() in seen:
            continue
        findings.append({"title": title, "body": body[:200]})
        seen.add(title.lower())
        if len(findings) >= limit:
            return findings

    return findings
