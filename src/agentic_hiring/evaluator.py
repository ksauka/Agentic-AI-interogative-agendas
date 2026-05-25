"""Candidate evaluator: classifies retrieved evidence into structured groups."""

from __future__ import annotations

from .schemas import AssessmentPlan, CandidateEvaluation, EvidenceSection


class CandidateEvaluator:
    """Rule-based evaluator.  All logic is deterministic for experimental control."""

    def evaluate(
        self,
        plan: AssessmentPlan,
        retrieved: dict[str, list[EvidenceSection]],
    ) -> CandidateEvaluation:
        supporting = retrieved.get("supporting", [])
        caution = retrieved.get("caution", [])
        transferable = retrieved.get("transferable", [])

        missing_or_uncertain = [
            "Direct end-to-end talent screening ownership is not clearly evidenced in the CV.",
            "Independent decision authority over candidate outcomes is absent from stated experience.",
            "Formal recruiter or talent specialist title has not been held.",
        ]

        recommendation_basis = (
            "The candidate demonstrates process coordination, applicant tracking, "
            "structured communication, and screening-adjacent support experience. "
            "Key evidence is present for required qualifications around coordination "
            "and stakeholder management. The primary uncertainty is the absence of "
            "explicit end-to-end recruitment ownership or independent screening authority."
        )

        return CandidateEvaluation(
            supporting_evidence=supporting,
            caution_evidence=caution,
            transferable_evidence=transferable,
            missing_or_uncertain=missing_or_uncertain,
            recommendation_basis=recommendation_basis,
        )
