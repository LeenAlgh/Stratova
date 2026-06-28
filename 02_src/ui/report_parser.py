"""Parse Stratova agent .txt reports into structured sections."""

import re
from dataclasses import dataclass


@dataclass
class ReportSection:
    title: str
    body: str


@dataclass
class ParsedReport:
    title: str
    meta: dict[str, str]
    sections: list[ReportSection]


def parse_report_txt(text: str) -> ParsedReport:
    lines = text.splitlines()
    title = lines[0].strip() if lines else "Report"
    meta: dict[str, str] = {}

    body_start = 0
    for i, line in enumerate(lines[1:], start=1):
        if line.strip().startswith("="):
            body_start = i + 1
            break
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()

    body = "\n".join(lines[body_start:])
    sections: list[ReportSection] = []
    pattern = re.compile(r"^([A-Z][A-Z0-9 \/&]+)\n-{10,}\n", re.MULTILINE)
    matches = list(pattern.finditer(body))

    if not matches:
        sections.append(ReportSection(title="Report", body=body.strip()))
        return ParsedReport(title=title, meta=meta, sections=sections)

    for idx, match in enumerate(matches):
        section_title = match.group(1).strip()
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(body)
        section_body = body[start:end].strip()
        sections.append(ReportSection(title=section_title, body=section_body))

    return ParsedReport(title=title, meta=meta, sections=sections)
