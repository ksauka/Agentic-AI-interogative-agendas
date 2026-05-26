"""Top-level agentic hiring decision agent.

Orchestrates the full pipeline:
    EvidenceStore → Planner → Retriever → Evaluator → Recommender → Renderer

All calls are deterministic; no LLM calls are made here.
"""

from __future__ import annotations

from pathlib import Path

from .conditions import Condition, get_condition
from .evaluator import CandidateEvaluator
from .evidence_store import EvidenceStore, build_evidence_store
from .planner import AssessmentPlanner
from .recommender import RecommendationPolicy
from .renderer import RecommendationRenderer
from .retriever import EvidenceRetriever
from .schemas import (
    AgentState,
    AssessmentPlan,
    ChallengeResponse,
    EvidenceSection,
    RecommendationState,
    RenderedResponse,
)

_DEFAULT_CASE = (
    Path(__file__).resolve().parents[2]
    / "study"
    / "materials"
    / "hiring_case"
    / "case.json"
)


class AgenticHiringDecisionAgent:
    """Bounded agentic pipeline for the hiring case study.

    Conditions (E×A×C) affect presentation only — the underlying evidence
    and recommendation are constant across all conditions.
    """

    def __init__(
        self,
        case_path: Path | str = _DEFAULT_CASE,
        condition: Condition | str | None = None,
    ) -> None:
        if isinstance(condition, str):
            condition = get_condition(condition)
        self.condition: Condition = condition or get_condition("E0_A0_C0")
        self.store: EvidenceStore = build_evidence_store(case_path)
        self._planner = AssessmentPlanner()
        self._retriever = EvidenceRetriever(self.store)
        self._evaluator = CandidateEvaluator()
        self._policy = RecommendationPolicy()
        self._renderer = RecommendationRenderer(self.store)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start_assessment(self, participant_id: str, case_id: str) -> AgentState:
        """Initialise a fresh AgentState for a new participant session."""
        plan = self._planner.create_initial_plan()
        return AgentState(
            condition_id=self.condition.condition_id,
            participant_id=participant_id,
            case_id=case_id,
            assessment_plan=plan,
        )

    def apply_stage1_steering(
        self,
        state: AgentState,
        selected_priorities: list[str],
        free_text: str = "",
    ) -> AgentState:
        """Incorporate Stage 1 user priorities into the assessment plan."""
        if state.assessment_plan is None:
            state.assessment_plan = self._planner.create_initial_plan()
        self._planner.update_with_user_priorities(
            state.assessment_plan, selected_priorities, free_text
        )
        state.stage1_priorities = list(selected_priorities)
        state.stage1_free_text = free_text.strip()
        return state

    def generate_recommendation(self, state: AgentState) -> AgentState:
        """Run the full evaluation pipeline and populate recommendation_state."""
        if state.assessment_plan is None:
            state.assessment_plan = self._planner.create_initial_plan()

        retrieved = self._retriever.retrieve_for_plan(state.assessment_plan)
        evaluation = self._evaluator.evaluate(state.assessment_plan, retrieved)
        recommendation = self._policy.recommend(evaluation, state.assessment_plan)
        rendered = self._renderer.render(
            recommendation,
            evaluation,
            self.condition,
            state.stage1_priorities,
            user_notes=state.stage1_free_text,
        )

        state.evaluation = evaluation
        state.recommendation_state = RecommendationState(
            recommendation=recommendation,
            rendered=rendered,
            user_priorities_used=list(state.stage1_priorities),
        )
        return state

    def handle_stage2_challenge(
        self,
        state: AgentState,
        challenge: str,
        custom_question: str = "",
    ) -> ChallengeResponse:
        """Generate a Stage 2 challenge response without changing recommendation."""
        query = custom_question if custom_question.strip() else challenge
        evidence = self._retriever.retrieve_for_challenge(query, top_k=5)
        response_text = self._renderer.render_challenge_response(
            challenge if challenge.lower() != "ask a custom question" else custom_question,
            evidence,
            self.condition,
        )
        result = ChallengeResponse(
            challenge=challenge,
            response_text=response_text,
            cited_sections=evidence,
        )
        state.challenge_history.append(result)
        return result

    # ── Evidence access ───────────────────────────────────────────────────────

    def get_section(self, evidence_id: str) -> EvidenceSection | None:
        return self.store.get(evidence_id)

    def get_document_sections(self, document_key: str) -> list[EvidenceSection]:
        return self.store.get_by_document(document_key)


# ── Factory ───────────────────────────────────────────────────────────────────

def create_decision_agent(
    case_path: Path | str = _DEFAULT_CASE,
    condition: Condition | str | None = None,
) -> AgenticHiringDecisionAgent:
    return AgenticHiringDecisionAgent(case_path=case_path, condition=condition)
