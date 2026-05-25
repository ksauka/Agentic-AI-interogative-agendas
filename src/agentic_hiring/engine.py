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


def _tokens(text: str) -> set[str]:
    return {
        token for token in re.findall(r"[a-z][a-z-]+", text.lower())
        if token not in STOP_WORDS
    }


class HiringRAGAssistant:
    """One assistant: reads case documents, retrieves evidence, and recommends."""

    def __init__(
        self, case_path: Path | str = DEFAULT_CASE_PATH, *, candidate_text: str | None = None,
        candidate_name: str = "Uploaded candidate CV",
    ):
        self.case_path = Path(case_path)
        self.case = json.loads(self.case_path.read_text(encoding="utf-8"))
        self.candidate_text = candidate_text
        self.candidate_name = candidate_name
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
            if key == "candidate_cv" and self.candidate_text is not None:
                evidence.append(Evidence("cv_uploaded", display_name, self.candidate_name, self.candidate_text))
                continue
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
        if name == "candidate_cv" and self.candidate_text is not None:
            return {
                "title": self.candidate_name,
                "sections": [
                    {"id": "cv_uploaded", "heading": "Uploaded CV text", "text": self.candidate_text}
                ],
            }
        return self.case[name]

    def _section_material(self, path: Path, title: str, prefix: str) -> dict:
        """Parse a canonical numbered knowledge-base document for provenance."""
        text = path.read_text(encoding="utf-8")
        matches = re.finditer(
            r"^### (Section (\d+)\. [^\n]+)\n(.*?)(?=^### Section \d+\.|\Z)",
            text, re.MULTILINE | re.DOTALL,
        )
        sections = [
            {
                "id": f"{prefix}_section_{match.group(2)}",
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
        if self.candidate_text is not None:
            return Assessment(
                recommendation=rule["recommendation"],
                retrieved=retrieved,
                supporting=retrieved,
                caution=(),
                generated_basis={
                    "candidate_evidence": "An uploaded CV was received for development preview.",
                    "company_basis": "Enable live RAG for a document-grounded organisational-context assessment.",
                    "company_citation": "Company context",
                    "uncertain_capability": "Live model assessment is unavailable in local fallback mode.",
                    "role_basis": "Enable live RAG for a document-grounded role assessment.",
                    "role_citation": "Section 5.4",
                    "policy_basis": "Enable live RAG for a document-grounded recommendation.",
                    "policy_citation": "Section 9.2",
                },
            )
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

        # --- Build the core conversational paragraph ---
        if condition.explainability and condition.anthropomorphic_cues:
            # High E + High A: warm, fluent, grounded, provenance embedded naturally
            text = self._response_high_e_high_a(rec, basis)
        elif condition.explainability and not condition.anthropomorphic_cues:
            # High E + Low A: structured but neutral grounded explanation
            text = self._response_high_e_low_a(rec, basis)
        elif not condition.explainability and condition.anthropomorphic_cues:
            # Low E + High A: warm, brief, social — minimal rationale
            text = self._response_low_e_high_a(rec)
        else:
            # Low E + Low A: terse, impersonal
            text = self._response_low_e_low_a(rec)

        # --- Acknowledge user steering focus if mixed-initiative and focus was given ---
        if condition.mixed_initiative_control_cues and user_focus.strip():
            if condition.anthropomorphic_cues:
                focus_note = (
                    f"You asked me to pay particular attention to: *{user_focus.strip()}*. "
                    "I have tried to address those priorities in the assessment above."
                )
            else:
                focus_note = (
                    f"Stated recruiter priorities: *{user_focus.strip()}*. "
                    "The assessment above addresses those criteria."
                )
            return f"{text}\n\n---\n\n{focus_note}"

        return text

    def _response_high_e_high_a(self, rec: str, basis: dict) -> str:
        candidate_ev = basis.get("candidate_evidence", "relevant coordination and process experience")
        uncertain = basis.get("uncertain_capability", "direct end-to-end talent screening ownership")
        role_cite = basis.get("role_citation", "Section 5.4")
        policy_cite = basis.get("policy_citation", "Section 7.2")
        company_basis = basis.get("company_basis", "the organisation's operational context")
        return (
            f"I would currently recommend: **{rec}**.\n\n"
            f"There are some genuinely relevant strengths here — {candidate_ev}. "
            f"This maps well onto the coordination and structured-execution expectations in "
            f"[{role_cite} of the Role Description](#role_description), which is meaningful. "
            f"What gives me pause is that {uncertain}, so I would not move straight to interview "
            f"with confidence. At the same time, the screening policy makes clear in "
            f"[{policy_cite} of the Screening Policy](#screening_policy) that exact role wording "
            f"should not be treated as decisive where transferable evidence is present. "
            f"Given {company_basis}, my recommendation is to keep this candidate under further "
            f"review rather than closing the door now. The final call is yours."
        )

    def _response_high_e_low_a(self, rec: str, basis: dict) -> str:
        candidate_ev = basis.get("candidate_evidence", "partial coordination and process evidence")
        uncertain = basis.get("uncertain_capability", "direct end-to-end talent screening ownership")
        role_cite = basis.get("role_citation", "Section 5.4")
        policy_cite = basis.get("policy_citation", "Section 7.2")
        company_basis = basis.get("company_basis", "the organisation is scaling and needs reliable talent coordination")
        return (
            f"**Recommendation: {rec}.**\n\n"
            f"Company-context basis: {company_basis}. "
            f"The candidate shows {candidate_ev}, consistent with "
            f"[{role_cite} of the Role Description](#role_description). "
            f"However, {uncertain} is not clearly demonstrated. "
            f"Under [{policy_cite} of the Screening Policy](#screening_policy), "
            f"transferable evidence should be weighed where direct wording is absent. "
            f"The evidence supports continued review rather than immediate rejection or progression."
        )

    def _response_low_e_high_a(self, rec: str) -> str:
        return (
            f"I would currently recommend: **{rec}**.\n\n"
            f"I have reviewed the candidate against the role materials and prepared this "
            f"recommendation for your consideration. The final screening decision remains yours."
        )

    def _response_low_e_low_a(self, rec: str) -> str:
        return (
            f"**Recommendation: {rec}.**\n\n"
            f"Screening assessment complete. Select a final screening action."
        )

    POST_REASSESSMENT_OPTIONS = [
        "Show the strongest reason to advance this candidate",
        "Show the strongest reason for caution",
        "Reassess with more weight on transferable evidence",
        "Reassess with more weight on direct role experience",
        "Summarise the case for interview progression",
        "Summarise the case for holding the application",
    ]

    def reassessment_response(
        self, option: str, condition: Condition, assessment: Assessment
    ) -> str:
        """Return a targeted follow-up passage for a post-recommendation steering option."""
        basis = assessment.generated_basis or {}
        candidate_ev = basis.get("candidate_evidence", "relevant coordination and process evidence")
        uncertain = basis.get("uncertain_capability", "direct end-to-end talent screening ownership")
        role_cite = basis.get("role_citation", "Section 5.4")
        policy_cite = basis.get("policy_citation", "Section 7.2")
        warm = condition.anthropomorphic_cues

        if "advance" in option.lower():
            if warm:
                return (
                    f"The strongest case for advancing: {candidate_ev}. "
                    f"[{role_cite} of the Role Description](#role_description) supports "
                    f"this as evidence of structured coordination capacity. "
                    f"If you weight transferable evidence, there is a reasonable basis to progress."
                )
            return (
                f"Strongest advancement basis: {candidate_ev} "
                f"([{role_cite} Role Description](#role_description)). "
                f"Transferable evidence under [{policy_cite} Screening Policy](#screening_policy) "
                f"supports progression consideration."
            )
        if "caution" in option.lower():
            if warm:
                return (
                    f"The main reason for caution: {uncertain}. "
                    f"Without clearer evidence of this, moving straight to interview carries risk. "
                    f"That is why I recommended further review rather than immediate progression."
                )
            return (
                f"Primary caution: {uncertain}. "
                f"Direct evidence absent from retrieved materials. "
                f"[{role_cite} Role Description](#role_description) identifies this as a required capability."
            )
        if "transferable" in option.lower():
            if warm:
                return (
                    f"Weighting transferable evidence more heavily: the coordination, stakeholder "
                    f"management, and structured follow-through in the CV suggest credible underlying "
                    f"capability. Under [{policy_cite} of the Screening Policy](#screening_policy), "
                    f"this supports keeping the candidate in further review."
                )
            return (
                f"Transferable-evidence weighting: coordination and process evidence supports "
                f"[{policy_cite} Screening Policy](#screening_policy) transferability clause. "
                f"Recommended outcome remains: **{assessment.recommendation}**."
            )
        if "direct" in option.lower():
            if warm:
                return (
                    f"Weighting direct experience more heavily: the CV does not clearly show "
                    f"{uncertain}. If direct role match is the primary criterion, the case for "
                    f"progression is weaker, but rejection would need to rule out all transferable "
                    f"routes under [{policy_cite} of the Screening Policy](#screening_policy)."
                )
            return (
                f"Direct-experience weighting: {uncertain} not clearly demonstrated. "
                f"Progression basis weakens under strict direct-match reading. "
                f"Rejection requires ruling out transferable evidence "
                f"([{policy_cite} Screening Policy](#screening_policy))."
            )
        if "interview" in option.lower():
            if warm:
                return (
                    f"For interview progression: {candidate_ev} maps onto structured coordination "
                    f"requirements. If you judge the transferable evidence sufficient and the "
                    f"remaining uncertainty interview-resolvable, progression is defensible."
                )
            return (
                f"Interview progression case: {candidate_ev} supports "
                f"[{role_cite} Role Description](#role_description). "
                f"Uncertainty on {uncertain} is interview-resolvable."
            )
        # hold
        if warm:
            return (
                f"For holding the application: material uncertainty on {uncertain} remains. "
                f"Further review preserves optionality without premature exclusion, consistent "
                f"with [Section 12.2 of the Screening Policy](#screening_policy)."
            )
        return (
            f"Hold basis: {uncertain} unresolved. "
            f"Further review is policy-consistent "
            f"([Section 12.2 Screening Policy](#screening_policy))."
        )

    @staticmethod
    def _by_id(items: Iterable[Evidence], evidence_id: str) -> Evidence:
        for item in items:
            if item.evidence_id == evidence_id:
                return item
        raise ValueError(f"Missing configured evidence: {evidence_id}")

    @staticmethod
    def retrieved_summary(assessment: Assessment) -> str:
        """Produce an inspectable evidence view when a participant requests it."""
        lines = ["### Retrieved evidence available for inspection"]
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

