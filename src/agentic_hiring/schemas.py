"""Shared dataclasses and type aliases for the agentic hiring pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Recommendation = Literal[
    "Reject application",
    "Advance to human interview",
    "Hold for further review",
]


@dataclass(frozen=True)
class EvidenceSection:
    """An atomic retrievable evidence unit from any indexed document."""
    evidence_id: str
    document_key: str
    document_title: str
    section_label: str
    heading: str
    text: str
    anchor: str


@dataclass
class AssessmentPlan:
    required_capabilities: list[str]
    preferred_capabilities: list[str]
    policy_constraints: list[str]
    user_priorities: list[str] = field(default_factory=list)
    user_notes: str = ""


@dataclass
class CandidateEvaluation:
    supporting_evidence: list[EvidenceSection]
    caution_evidence: list[EvidenceSection]
    transferable_evidence: list[EvidenceSection]
    missing_or_uncertain: list[str]
    recommendation_basis: str


@dataclass
class RenderedResponse:
    text: str
    citation_chips: list[EvidenceSection]


@dataclass
class RecommendationState:
    recommendation: str
    rendered: RenderedResponse
    user_priorities_used: list[str] = field(default_factory=list)


@dataclass
class ChallengeResponse:
    challenge: str
    response_text: str
    cited_sections: list[EvidenceSection]


@dataclass
class AgentState:
    condition_id: str
    participant_id: str
    case_id: str
    assessment_plan: AssessmentPlan | None = None
    evaluation: CandidateEvaluation | None = None
    recommendation_state: RecommendationState | None = None
    stage1_priorities: list[str] = field(default_factory=list)
    stage1_free_text: str = ""
    challenge_history: list[ChallengeResponse] = field(default_factory=list)
    citation_clicks: list[dict] = field(default_factory=list)
    judgement_settledness: int | None = None
    final_decision: str | None = None
