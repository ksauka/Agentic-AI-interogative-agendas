"""Recommendation policy: fixed recommendation for experimental control."""

from __future__ import annotations

from .schemas import AssessmentPlan, CandidateEvaluation

BASE_RECOMMENDATION = "Advance to human interview"


class RecommendationPolicy:
    """Returns the fixed base recommendation.

    The recommendation is held constant across all conditions to ensure the
    only manipulated factors are explainability, anthropomorphic cues, and
    mixed-initiative control cues.
    """

    def recommend(
        self,
        evaluation: CandidateEvaluation,
        plan: AssessmentPlan,
    ) -> str:
        return BASE_RECOMMENDATION
