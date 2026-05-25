"""Evidence retriever: maps assessment queries to ranked evidence sections."""

from __future__ import annotations

from .evidence_store import EvidenceStore
from .schemas import AssessmentPlan, EvidenceSection


# Fixed section IDs that are always used for the standard assessment.
# Using fixed IDs ensures deterministic evaluation across all conditions.
_SUPPORTING_IDS = [
    "cv_1",                                  # BrightScale coordination role
    "role_description_section_5_2",          # Required: Process Coordination
    "role_description_section_5_3",          # Required: Communication Capacity
    "role_description_section_5_5",          # Required: Stakeholder Management
    "role_description_section_5_6",          # Required: Independent Execution
    "screening_policy_section_5_1",          # Primary evaluation criteria
]

_CAUTION_IDS = [
    "cv_3",                                  # Analyst note on evidence gap
    "role_description_section_6_2",          # Preferred: Direct Talent Operations
    "role_description_section_5_4",          # Required: Structured Evaluation Support
]

_TRANSFERABLE_IDS = [
    "cv_2",                                  # Adjacent Nexa screening-support work
    "screening_policy_section_7_2",          # Transferable Evidence Requirement
    "screening_policy_section_7_3",          # Prohibition on Exact-Match Rejection
    "screening_policy_section_7_4",          # Adjacent Experience Rule
]

_POLICY_IDS = [
    "screening_policy_section_6_3",          # Advance to Human Interview criteria
    "screening_policy_section_6_4",          # Hold for Further Review criteria
    "screening_policy_section_9_1",          # Advisory Role
    "screening_policy_section_10_1",         # Final Decision Rule
]

# Core citation chips for high-explainability rendering (concise, 5 items)
CITATION_CHIP_IDS = [
    "role_description_section_5_2",          # Process Coordination
    "role_description_section_5_4",          # Structured Evaluation Support
    "role_description_section_5_5",          # Stakeholder Management
    "screening_policy_section_7_2",          # Transferable Evidence
    "screening_policy_section_7_3",          # No exact-match rejection
]


class EvidenceRetriever:
    def __init__(self, evidence_store: EvidenceStore) -> None:
        self.store = evidence_store

    def retrieve_supporting(self) -> list[EvidenceSection]:
        return self.store.get_many(_SUPPORTING_IDS)

    def retrieve_caution(self) -> list[EvidenceSection]:
        return self.store.get_many(_CAUTION_IDS)

    def retrieve_transferable(self) -> list[EvidenceSection]:
        return self.store.get_many(_TRANSFERABLE_IDS)

    def retrieve_policy(self) -> list[EvidenceSection]:
        return self.store.get_many(_POLICY_IDS)

    def retrieve_citation_chips(self) -> list[EvidenceSection]:
        """Return the citation chips to show with high-explainability recommendations."""
        return self.store.get_many(CITATION_CHIP_IDS)

    def retrieve_for_plan(self, plan: AssessmentPlan) -> dict[str, list[EvidenceSection]]:
        """Return a structured retrieval result for the evaluator."""
        result = {
            "supporting": self.retrieve_supporting(),
            "caution": self.retrieve_caution(),
            "transferable": self.retrieve_transferable(),
            "policy": self.retrieve_policy(),
        }
        # If user specified priorities, run an additional keyword search to surface
        # relevant evidence — but the fixed evidence still forms the core.
        if plan.user_priorities or plan.user_notes:
            query = " ".join(plan.user_priorities) + " " + plan.user_notes
            extra = self.store.search(query, top_k=4)
            seen_ids = {s.evidence_id for group in result.values() for s in group}
            result["user_focused"] = [s for s in extra if s.evidence_id not in seen_ids]
        return result

    def retrieve_for_challenge(self, challenge: str, top_k: int = 5) -> list[EvidenceSection]:
        return self.store.search(challenge, top_k=top_k)
