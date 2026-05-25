"""Document parsing and evidence retrieval store.

Parses knowledge-base markdown files into subsection-level EvidenceSection
objects and provides keyword-scored search.  All parsing is deterministic —
no randomness is introduced here.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .schemas import EvidenceSection

# ── Paths ─────────────────────────────────────────────────────────────────────

_BASE = Path(__file__).resolve().parents[2]
_KB = _BASE / "study" / "materials" / "knowledge_base"
_CASE = _BASE / "study" / "materials" / "hiring_case" / "case.json"

DOCUMENT_REGISTRY: dict[str, tuple[Path, str]] = {
    "company_context": (
        _KB / "company_context.md",
        "Company Context — Northstar Health Analytics",
    ),
    "role_description": (
        _KB / "strategic_talent_operations_partner_role_description.md",
        "Role Description — Strategic Talent Operations Partner",
    ),
    "screening_policy": (
        _KB / "ai_assisted_strategic_hiring_screening_policy.md",
        "Screening Policy — AI-Assisted Strategic Hiring",
    ),
}


# ── Parsers ───────────────────────────────────────────────────────────────────

def _section_to_anchor(document_key: str, major: str, minor: str) -> str:
    return f"{document_key}_section_{major}_{minor}"


def parse_markdown_document(
    path: Path, document_key: str, document_title: str
) -> list[EvidenceSection]:
    """Parse a numbered-markdown document into subsection EvidenceSection objects.

    Expected format: lines of the form
        **X.Y Title text.** Content sentence(s) here.
    where X is the major section number and Y the subsection number.
    """
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(
        r"^\*\*(\d+)\.(\d+)\s+([^*]+?)\.\*\*\s+(.*)",
        re.MULTILINE,
    )
    sections: list[EvidenceSection] = []
    for m in pattern.finditer(text):
        major, minor = m.group(1), m.group(2)
        title = m.group(3).strip()
        body = m.group(4).strip()
        evidence_id = _section_to_anchor(document_key, major, minor)
        sections.append(
            EvidenceSection(
                evidence_id=evidence_id,
                document_key=document_key,
                document_title=document_title,
                section_label=f"Section {major}.{minor}",
                heading=f"Section {major}.{minor}: {title}",
                text=body,
                anchor=evidence_id,
            )
        )
    return sections


def parse_candidate_cv(case_path: Path) -> list[EvidenceSection]:
    """Parse candidate CV sections from case.json."""
    data = json.loads(case_path.read_text(encoding="utf-8"))
    cv = data["candidate_cv"]
    title = cv.get("title", "Candidate CV")
    sections: list[EvidenceSection] = []
    for i, sec in enumerate(cv["sections"], 1):
        evidence_id = sec["id"]
        sections.append(
            EvidenceSection(
                evidence_id=evidence_id,
                document_key="candidate_cv",
                document_title=title,
                section_label=f"CV {i}",
                heading=sec["heading"],
                text=sec["text"],
                anchor=evidence_id,
            )
        )
    return sections


# ── Evidence store ────────────────────────────────────────────────────────────

class EvidenceStore:
    """In-memory evidence store backed by all fixed case documents."""

    def __init__(self, sections: list[EvidenceSection]) -> None:
        self.sections = sections
        self._by_id: dict[str, EvidenceSection] = {s.evidence_id: s for s in sections}
        self._by_doc: dict[str, list[EvidenceSection]] = {}
        for s in sections:
            self._by_doc.setdefault(s.document_key, []).append(s)

    def get(self, evidence_id: str) -> EvidenceSection | None:
        return self._by_id.get(evidence_id)

    def get_by_document(self, document_key: str) -> list[EvidenceSection]:
        return self._by_doc.get(document_key, [])

    def get_many(self, evidence_ids: list[str]) -> list[EvidenceSection]:
        return [s for eid in evidence_ids if (s := self._by_id.get(eid)) is not None]

    def search(self, query: str, top_k: int = 8) -> list[EvidenceSection]:
        """Return top-k sections by keyword overlap with query."""
        stop = {"the", "a", "an", "and", "or", "of", "in", "to", "for",
                "is", "are", "where", "that", "this", "with", "shall", "not",
                "may", "be", "on", "at", "by", "it", "its", "has", "have"}
        query_words = set(re.findall(r"\w+", query.lower())) - stop
        scored: list[tuple[int, EvidenceSection]] = []
        for s in self.sections:
            text_words = set(re.findall(r"\w+", (s.text + " " + s.heading).lower())) - stop
            overlap = len(query_words & text_words)
            if overlap > 0:
                scored.append((overlap, s))
        scored.sort(key=lambda x: -x[0])
        return [s for _, s in scored[:top_k]]


# ── Factory ───────────────────────────────────────────────────────────────────

def build_evidence_store(case_path: Path | str = _CASE) -> EvidenceStore:
    """Parse all fixed documents and return a populated EvidenceStore."""
    all_sections: list[EvidenceSection] = []
    for doc_key, (path, title) in DOCUMENT_REGISTRY.items():
        if path.exists():
            all_sections.extend(parse_markdown_document(path, doc_key, title))
    all_sections.extend(parse_candidate_cv(Path(case_path)))
    return EvidenceStore(all_sections)
