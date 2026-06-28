"""Shared parsing for markdown bullet fields in strategy UI JSON."""

from __future__ import annotations

import re

_BULLET_FIELD_RE = re.compile(r"^[-*]\s+\*\*(.+?)\*\*\s*:?\s*(.*)$")
_PLAIN_BULLET_RE = re.compile(r"^[-*]\s+(.*)$")


def _format_sub_bullet(line: str) -> str:
    stripped = line.strip()
    match = _BULLET_FIELD_RE.match(stripped)
    if match:
        label = match.group(1).strip().rstrip(":")
        value = match.group(2).strip()
        return f"{label}: {value}" if value else label
    plain = _PLAIN_BULLET_RE.match(stripped)
    if plain:
        return plain.group(1).strip()
    return stripped


def parse_flat_bullet_fields(body: str) -> dict[str, str]:
    """Parse `- **Label**: value` lines at any indentation level."""
    fields: dict[str, str] = {}
    for line in (body or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        match = _BULLET_FIELD_RE.match(stripped)
        if not match:
            continue
        key = match.group(1).strip().rstrip(":")
        value = match.group(2).strip()
        fields[key.lower()] = value
    return fields


def parse_bullet_fields(body: str) -> dict[str, str]:
    """
    Parse markdown bullet fields, including nested sub-bullets.

    Supports:
    - `- **Label:** value`
    - `- **Label**: value`
    - `- **Label**:` followed by indented sub-bullets
    """
    fields: dict[str, str] = {}
    lines = (body or "").splitlines()
    index = 0

    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        if line.startswith((" ", "\t")):
            index += 1
            continue

        match = _BULLET_FIELD_RE.match(line.strip())
        if not match:
            index += 1
            continue

        key = match.group(1).strip().rstrip(":").lower()
        value = match.group(2).strip()
        index += 1

        sub_items: list[str] = []
        while index < len(lines):
            sub_line = lines[index]
            if not sub_line.strip():
                index += 1
                continue
            if not sub_line.startswith((" ", "\t")):
                break
            if sub_line.strip().startswith(("-", "*")):
                sub_items.append(_format_sub_bullet(sub_line))
            index += 1

        if sub_items:
            combined = "; ".join(item for item in sub_items if item)
            if value:
                combined = f"{value}; {combined}" if combined else value
        else:
            combined = value

        fields[key] = combined

    return fields
