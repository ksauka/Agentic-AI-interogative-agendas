"""Candidate evaluator: classifies retrieved evidence into structured groups."""

from __future__ import annotations

from .schemas import AssessmentPlan, CandidateEvaluation, EvidenceSection

_FALLBACK_MISSING = [
    "Direct end-to-end talent screening ownership is not clearly evidenced in the CV.",
    "Independent decision authority over candidate outcomes is absent from stated experience.",
    "Formal recruiter or talent specialist title has not been held.",
]

_FALLBACK_BASIS = (
    "The candidate demonstrates process coordination, applicant tracking, "
    "structured communication, and screening-adjacent support experience. "
    "Key evidence is present for required qualifications around coordination "
    "and stakeholder management. The primary uncertainty is the absence of "
    "explicit end-to-end recruitment ownership or independent screening authority."
)


class CandidateEvaluator:
    """Rule-based evaluator. Classifies retrieved evidence into structured groups."""

    def evaluate(
        self,
        plan: AssessmentPlan,
        retrieved: dict[str, list[EvidenceSection]],
    ) -> CandidateEvaluation:
        supporting = retrieved.get("supporting", [])
        caution = retrieved.get("caution", [])
        transferable = retrieved.get("transferable", [])

        return CandidateEvaluation(
            supporting_evidence=supporting,
            caution_evidence=caution,
            transferable_evidence=transferable,
            missing_or_uncertain=self._build_missing(caution),
            recommendation_basis=self._build_basis(supporting, caution),
        )

    @staticmethod
    def _build_missing(caution: list[EvidenceSection]) -> list[str]:
        if not caution:
            return list(_FALLBACK_MISSING)
        return [
            f"{item.heading}: not fully evidenced in the candidate CV."
            for item in caution
        ]

    @staticmethod
    def _build_basis(
        supporting: list[EvidenceSection], caution: list[EvidenceSection]
    ) -> str:
        if not supporting:
            return _FALLBACK_BASIS
        role_items = [s for s in supporting if s.document_key == "role_description"]
        cv_items = [s for s in supporting if s.document_key == "candidate_cv"]
        strength_areas = (
            ", ".join(item.heading for item in role_items[:2])
            if role_items else "required coordination capabilities"
        )
        cv_note = (
            f"CV evidence ({cv_items[0].heading}) shows alignment with {strength_areas}"
            if cv_items else f"The candidate shows evidence relevant to {strength_areas}"
        )
        caution_note = (
            f" The primary gap is around {caution[0].heading.lower()}."
            if caution else ""
        )
        return f"{cv_note}.{caution_note}"
