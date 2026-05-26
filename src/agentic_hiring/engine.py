"""Deterministic retrieval-grounded decision pipeline for the hiring study."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .conditions import Condition


DEFAULT_CASE_PATH = (
    Path(__file__).resolve().parents[2] / "study" / "materials" / "hiring_case" / "case.json"
)
DEFAULT_POLICY_PATH = (
    Path(__file__).resolve().parents[2] / "study" / "materials" / "knowledge_base"
    / "ai_assisted_strategic_hiring_screening_policy.md"
)
DEFAULT_ROLE_PATH = (
    Path(__file__).resolve().parents[2] / "study" / "materials" / "knowledge_base"
    / "strategic_talent_operations_partner_role_description.md"
)
STOP_WORDS = {
    "a", "an", "and", "as", "at", "be", "by", "for", "from", "in", "is", "of",
    "on", "or", "the", "this", "to", "with", "where", "rather", "than",
}


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    document: str
    heading: str
    text: str
    score: float = 0.0


@dataclass(frozen=True)
class Assessment:
    recommendation: str
    retrieved: tuple[Evidence, ...]
    supporting: tuple[Evidence, ...]
    caution: tuple[Evidence, ...]
    generated_basis: dict[str, str] | None = None
    retrieval_backend: str = "lexical_fallback"
    generation_backend: str = "protocol_fallback"


@dataclass(frozen=True)
class Citation:
    """Section-level citation for embedding in recommendation text."""
    label: str       # e.g. "Section 5.2 of the Role Description"
    section_id: str  # e.g. "role_section_5_2"
    text: str = ""   # excerpt for click-logging

    @property
    def link(self) -> str:
        return f"[{self.label}](#{self.section_id})"


def citation_link(label: str, section_id: str) -> str:
    """Return a markdown link to a section anchor."""
    return f"[{label}](#{section_id})"


def _tokens(text: str) -> set[str]:
    return {
        token for token in re.findall(r"[a-z][a-z-]+", text.lower())
        if token not in STOP_WORDS
    }


class HiringRAGAssistant:
    """One assistant: reads case documents, retrieves evidence, and recommends."""

    def __init__(self, case_path: Path | str = DEFAULT_CASE_PATH) -> None:
        self.case_path = Path(case_path)
        self.case = json.loads(self.case_path.read_text(encoding="utf-8"))
        self.policy_path = DEFAULT_POLICY_PATH
        self.role_path = DEFAULT_ROLE_PATH
        self.documents = self._flatten_documents()

    def _flatten_documents(self) -> tuple[Evidence, ...]:
        document_names = {
            "company_context": "Company context",
            "role_description": "Role Description for Strategic Talent Operations Partner",
            "screening_policy": "AI-Assisted Strategic Hiring Screening Policy",
            "candidate_cv": "Candidate CV",
        }
        evidence = []
        for key, display_name in document_names.items():
            if key == "screening_policy":
                source = self._policy_material()
            elif key == "role_description":
                source = self._role_material()
            else:
                source = self.case[key]
            for section in source["sections"]:
                evidence.append(
                    Evidence(section["id"], display_name, section["heading"], section["text"])
                )
        return tuple(evidence)

    def material(self, name: str) -> dict:
        """Expose an inspectable internal or candidate document."""
        if name == "screening_policy":
            return self._policy_material()
        if name == "role_description":
            return self._role_material()
        return self.case[name]

    def _section_material(self, path: Path, title: str, prefix: str) -> dict:
        """Parse a canonical numbered knowledge-base document for provenance."""
        text = path.read_text(encoding="utf-8")
        matches = re.finditer(
            r"^#{2,4}\s+(Section\s+(\d+(?:\.\d+)?)\.\s+[^\n]+)\n(.*?)(?=^#{2,4}\s+Section\s+\d+(?:\.\d+)?\.)|\Z)",
            text, re.MULTILINE | re.DOTALL,
        )
        sections = [
            {
                "id": f"{prefix}_section_{match.group(2).replace('.', '_')}",
                "heading": match.group(1),
                "text": match.group(3).strip(),
            }
            for match in matches
        ]
        if not sections:
            raise ValueError(f"No numbered sections were parsed from {title}.")
        return {"title": title, "sections": sections}

    def _policy_material(self) -> dict:
        return self._section_material(
            self.policy_path, "AI-Assisted Strategic Hiring Screening Policy", "policy"
        )

    def _role_material(self) -> dict:
        return self._section_material(
            self.role_path, "Role Description for Strategic Talent Operations Partner", "role"
        )

    def retrieve(self, query: str, top_k: int = 8) -> tuple[Evidence, ...]:
        """Retrieve grounded sections using transparent sparse lexical matching."""
        query_tokens = _tokens(query)
        scored = []
        for evidence in self.documents:
            terms = _tokens(f"{evidence.heading} {evidence.text}")
            overlap = query_tokens & terms
            score = sum(1.0 + math.log(1 + len(term)) for term in overlap)
            if score:
                scored.append(
                    Evidence(
                        evidence.evidence_id,
                        evidence.document,
                        evidence.heading,
                        evidence.text,
                        round(score, 3),
                    )
                )
        scored.sort(key=lambda item: (-item.score, item.evidence_id))
        return tuple(scored[:top_k])

    def assess(self, user_focus: str = "") -> Assessment:
        """Run the shared retrieval-grounded decision step for every condition."""
        rule = self.case["fixed_assessment"]
        retrieved = self.retrieve(rule["retrieval_query"], top_k=len(self.documents))
        retrieved_by_id = {item.evidence_id: item for item in retrieved}

        def selected(ids: Iterable[str]) -> tuple[Evidence, ...]:
            missing = [evidence_id for evidence_id in ids if evidence_id not in retrieved_by_id]
            if missing:
                raise ValueError(f"Configured evidence was not retrieved: {missing}")
            return tuple(retrieved_by_id[evidence_id] for evidence_id in ids)

        return Assessment(
            recommendation=rule["recommendation"],
            retrieved=retrieved,
            supporting=selected(rule["supporting_ids"]),
            caution=selected(rule["caution_ids"]),
        )

    def response(self, condition: Condition, assessment: Assessment | None = None, user_focus: str = "") -> str:
        """Render one conversational recommendation paragraph under a condition's overlays."""
        assessment = assessment or self.assess()
        basis = assessment.generated_basis or {}
        rec = assessment.recommendation

        if condition.explainability and condition.anthropomorphic_cues:
            return self._response_high_e_high_a(rec, basis, user_focus)
        elif condition.explainability and not condition.anthropomorphic_cues:
            return self._response_high_e_low_a(rec, basis, user_focus)
        elif not condition.explainability and condition.anthropomorphic_cues:
            return self._response_low_e_high_a(rec, user_focus)
        else:
            return self._response_low_e_low_a(rec, user_focus)

    def _response_high_e_high_a(self, rec: str, basis: dict, user_focus: str = "") -> str:
        candidate_ev = basis.get("candidate_evidence", "relevant coordination and process experience")
        uncertain = basis.get("uncertain_capability", "direct end-to-end talent screening ownership")
        role_cite = basis.get("role_citation", "Section 5.2")
        policy_cite = basis.get("policy_citation", "Section 7.2")
        company_basis = basis.get("company_basis", "the organisation's operational context")
        role_anchor = self._make_anchor(role_cite, "role")
        policy_anchor = self._make_anchor(policy_cite, "policy")
        preamble = (
            f"You asked me to pay particular attention to {user_focus.strip()}. "
            f"Looking at the CV through that lens, "
        ) if user_focus.strip() else ""
        return (
            f"{preamble}I would keep this candidate in consideration rather than screen them out at this stage. "
            f"There is meaningful evidence of {candidate_ev}, which fits important parts of this role — "
            f"especially the coordination and independent execution expectations in "
            f"[{role_cite} of the Role Description](#{role_anchor}). "
            f"What gives me pause is that {uncertain}, so I would not move straight to interview with confidence. "
            f"At the same time, the screening policy makes clear in "
            f"[{policy_cite} of the Screening Policy](#{policy_anchor}) that exact role wording "
            f"should not be treated as decisive where transferable evidence is present. "
            f"Given {company_basis}, my recommendation is **{rec}** — "
            f"{self._action_phrase(rec)}. The final call is yours."
        )

    def _response_high_e_low_a(self, rec: str, basis: dict, user_focus: str = "") -> str:
        candidate_ev = basis.get("candidate_evidence", "partial coordination and process evidence")
        uncertain = basis.get("uncertain_capability", "direct end-to-end talent screening ownership")
        role_cite = basis.get("role_citation", "Section 5.2")
        policy_cite = basis.get("policy_citation", "Section 7.2")
        company_basis = basis.get("company_basis", "the organisation is scaling and needs reliable talent coordination")
        role_anchor = self._make_anchor(role_cite, "role")
        policy_anchor = self._make_anchor(policy_cite, "policy")
        focus_note = f"Stated priorities: *{user_focus.strip()}*. " if user_focus.strip() else ""
        return (
            f"{focus_note}**Assessment:** The candidate shows {candidate_ev}, consistent with "
            f"[{role_cite} of the Role Description](#{role_anchor}). "
            f"However, {uncertain} is not clearly demonstrated. "
            f"Company context: {company_basis}. "
            f"Under [{policy_cite} of the Screening Policy](#{policy_anchor}), "
            f"transferable evidence should be weighed where direct wording is absent.\n\n"
            f"**Recommended action: {rec}.**"
        )

    def _response_low_e_high_a(self, rec: str, user_focus: str = "") -> str:
        focus_note = f"You asked me to focus on: *{user_focus.strip()}*. " if user_focus.strip() else ""
        return (
            f"{focus_note}I have reviewed the candidate against the role materials. "
            f"There are some relevant strengths here, though the picture is not entirely clear-cut. "
            f"My recommendation is **{rec}**.\n\n"
            f"The final screening decision remains yours."
        )

    def _response_low_e_low_a(self, rec: str, user_focus: str = "") -> str:
        if "Advance" in rec:
            assessment_text = "The candidate meets enough screening criteria for progression."
        elif "Hold" in rec:
            assessment_text = "Available evidence is incomplete for an immediate progression decision."
        else:
            assessment_text = "The candidate does not meet the screening threshold for progression."
        focus_note = f"Priorities noted: *{user_focus.strip()}*. " if user_focus.strip() else ""
        return f"{focus_note}**Assessment:** {assessment_text}\n\n**Recommended action: {rec}.**"

    @staticmethod
    def _action_phrase(rec: str) -> str:
        if "Advance" in rec:
            return "moving the candidate to a human interview while using the interview to test the remaining uncertainty"
        if "Hold" in rec:
            return "keeping the application under further review before making a progression decision"
        return "not progressing the application at this stage"

    @staticmethod
    def _make_anchor(citation_str: str, prefix: str) -> str:
        """First section number in citation string → anchor ID. 'Section 5.2' + 'role' → 'role_section_5_2'."""
        match = re.search(r"Section\s+(\d+(?:\.\d+)?)", citation_str)
        if match:
            return f"{prefix}_section_{match.group(1).replace('.', '_')}"
        return prefix

    POST_REASSESSMENT_OPTIONS = [
        "Show the strongest reason to advance the candidate",
        "Show the strongest reason for caution",
        "Identify which requirements remain uncertain",
        "Explain what information is still missing",
        "Reassess using a stricter interpretation of the screening policy",
        "Reassess using more weight on transferable evidence",
    ]

    def reassessment_response(
        self, option: str, condition: Condition, assessment: Assessment
    ) -> str:
        """Return a targeted follow-up passage for a post-recommendation challenge option."""
        basis = assessment.generated_basis or {}
        candidate_ev = basis.get("candidate_evidence", "relevant coordination and process experience")
        uncertain = basis.get("uncertain_capability", "direct end-to-end talent screening ownership")
        role_cite = basis.get("role_citation", "Section 5.4")
        policy_cite = basis.get("policy_citation", "Section 7.2")
        warm = condition.anthropomorphic_cues
        role_anchor = self._make_anchor(role_cite, "role")
        policy_anchor = self._make_anchor(policy_cite, "policy")
        opt = option.lower()

        if "advance" in opt:
            if warm:
                return (
                    f"The strongest case for advancing: {candidate_ev}. "
                    f"[{role_cite} of the Role Description](#{role_anchor}) supports "
                    f"this as evidence of structured coordination capacity. "
                    f"If you weight transferable evidence, there is a reasonable basis to progress."
                )
            return (
                f"Strongest advancement basis: {candidate_ev} "
                f"([{role_cite} Role Description](#{role_anchor})). "
                f"Transferable evidence under [{policy_cite} Screening Policy](#{policy_anchor}) "
                f"supports progression consideration."
            )

        if "caution" in opt:
            if warm:
                return (
                    f"The main reason for caution: {uncertain}. "
                    f"Without clearer evidence of this, moving straight to interview carries risk. "
                    f"That is why I recommended further review rather than immediate progression."
                )
            return (
                f"Primary caution: {uncertain}. "
                f"Direct evidence absent from retrieved materials. "
                f"[{role_cite} Role Description](#{role_anchor}) identifies this as a required capability."
            )

        if "uncertain" in opt:
            if warm:
                return (
                    f"The requirements that remain uncertain are primarily around {uncertain}. "
                    f"[{role_cite} of the Role Description](#{role_anchor}) sets expectations "
                    f"that the CV does not clearly address. An interview would be the natural next "
                    f"step to test whether the underlying capability is present."
                )
            return (
                f"Uncertain requirement: {uncertain}. "
                f"Not clearly evidenced against [{role_cite} Role Description](#{role_anchor}). "
                f"An interview would be required to verify."
            )

        if "missing" in opt:
            if warm:
                return (
                    f"The main information still missing: direct evidence of {uncertain}. "
                    f"The CV shows coordination and process work, but does not confirm independent "
                    f"end-to-end ownership of screening decisions. That gap is the main source of "
                    f"ambiguity in the current assessment."
                )
            return (
                f"Missing information: direct evidence of {uncertain}. "
                f"CV provides coordination evidence but does not confirm independent screening authority."
            )

        if "stricter" in opt:
            if warm:
                return (
                    f"Under a stricter reading of the screening policy, the absence of direct "
                    f"end-to-end talent screening experience would weigh more heavily. "
                    f"[{policy_cite} of the Screening Policy](#{policy_anchor}) allows "
                    f"transferable evidence to substitute for direct wording, but a strict "
                    f"reading would require more explicit evidence before progression."
                )
            return (
                f"Stricter policy reading: [{policy_cite} Screening Policy](#{policy_anchor}) "
                f"transferability clause requires credible capability signal. "
                f"Under strict interpretation, {uncertain} gap weakens the progression case."
            )

        if "transferable" in opt:
            if warm:
                return (
                    f"Weighting transferable evidence more heavily: the coordination, stakeholder "
                    f"management, and structured follow-through in the CV suggest credible underlying "
                    f"capability. Under [{policy_cite} of the Screening Policy](#{policy_anchor}), "
                    f"this supports keeping the candidate in further review."
                )
            return (
                f"Transferable-evidence weighting: coordination and process evidence supports "
                f"[{policy_cite} Screening Policy](#{policy_anchor}) transferability clause. "
                f"Recommended outcome remains: **{assessment.recommendation}**."
            )

        # Default fallback
        if warm:
            return (
                f"For holding the application: material uncertainty on {uncertain} remains. "
                f"Further review preserves optionality without premature exclusion, consistent "
                f"with [Section 6.4 of the Screening Policy](#policy_section_6_4)."
            )
        return (
            f"Hold basis: {uncertain} unresolved. "
            f"Further review is policy-consistent "
            f"([Section 6.4 Screening Policy](#policy_section_6_4))."
        )

    @staticmethod
    def _by_id(items: Iterable[Evidence], evidence_id: str) -> Evidence:
        for item in items:
            if item.evidence_id == evidence_id:
                return item
        raise ValueError(f"Missing configured evidence: {evidence_id}")

    @staticmethod
    def debug_retrieved_summary(assessment: Assessment) -> str:
        """Developer tool: inspectable evidence view. NOT for participant-facing UI."""
        lines = ["### [DEBUG] Retrieved evidence"]
        for item in assessment.retrieved[:5]:
            lines.append(f"- **{item.document} — {item.heading}:** {item.text}")
        return "\n".join(lines)

    @staticmethod
    def audit_flags(condition: Condition) -> dict[str, bool]:
        """Record assigned treatment delivery fields for recommendation turns."""
        return {
            "rationale_present": condition.explainability,
            "first_person_present": condition.anthropomorphic_cues,
            "cooperative_cue_present": condition.anthropomorphic_cues,
            "checkpoint_present": condition.mixed_initiative_control_cues,
            "options_present": condition.mixed_initiative_control_cues,
            "decision_right_reminder_present": condition.mixed_initiative_control_cues,
            "steering_input_present": condition.mixed_initiative_control_cues,
            "post_recommendation_steering_present": condition.mixed_initiative_control_cues,
        }

    @staticmethod
    def backend_fields(assessment: Assessment) -> dict[str, str]:
        return {
            "retrieval_backend": assessment.retrieval_backend,
            "generation_backend": assessment.generation_backend,
        }

