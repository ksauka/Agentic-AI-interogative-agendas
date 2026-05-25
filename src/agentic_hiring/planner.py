"""Assessment planner: builds the capability checklist used for evaluation."""

from __future__ import annotations

from .schemas import AssessmentPlan


class AssessmentPlanner:
    """Creates and updates assessment plans for the fixed hiring case."""

    def create_initial_plan(self) -> AssessmentPlan:
        return AssessmentPlan(
            required_capabilities=[
                "process coordination",
                "structured screening or evaluation support",
                "stakeholder communication",
                "independent execution",
                "fast-paced SME environment experience",
            ],
            preferred_capabilities=[
                "direct recruitment coordination",
                "end-to-end screening ownership",
                "applicant tracking system exposure",
                "workflow improvement experience",
            ],
            policy_constraints=[
                "consider transferable evidence",
                "avoid exact keyword matching",
                "acknowledge uncertainty where present",
                "preserve human decision authority",
            ],
        )

    def update_with_user_priorities(
        self,
        plan: AssessmentPlan,
        selected_priorities: list[str],
        free_text: str,
    ) -> AssessmentPlan:
        """Incorporate Stage 1 user steering into the assessment plan."""
        plan.user_priorities = list(selected_priorities)
        plan.user_notes = free_text.strip()
        return plan
