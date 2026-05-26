"""Recommendation policy: dynamic when HIC input is present."""

from __future__ import annotations

from .schemas import AssessmentPlan, CandidateEvaluation

BASE_RECOMMENDATION = "Advance to human interview"

# Capability areas where this candidate's evidence is genuinely thin.
# When a recruiter actively flags any of these through HIC Stage 1, it signals
# a concern the available documents cannot resolve — the recommendation must
# reflect that rather than override the recruiter's explicit judgement.
_UNCERTAIN_AREAS = frozenset({
    "Independent ownership",
    "Structured evaluation or screening experience",
})


class RecommendationPolicy:
    """Recommendation policy — dynamic when HIC input is present.

    Without HIC input (C=0 or recruiter did not engage):
        Always returns BASE_RECOMMENDATION ("Advance to human interview").

    With HIC input (C=1, recruiter provided priorities):
        Returns "Hold for further review" if the recruiter flagged at least
        one area where this candidate's evidence is demonstrably thin.
        A single flagged evidence gap is sufficient — the HICs are not
        decorative, and the recruiter's concern must change the outcome.
    """

    def recommend(
        self,
        evaluation: CandidateEvaluation,
        plan: AssessmentPlan,
        hic_active: bool = False,
    ) -> str:
        if hic_active and plan.user_priorities:
            flagged_uncertain = sum(
                1 for p in plan.user_priorities if p in _UNCERTAIN_AREAS
            )
            if flagged_uncertain >= 1:
                return "Hold for further review"
        return BASE_RECOMMENDATION
