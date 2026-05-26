"""Recommendation renderer.

Produces condition-appropriate text and citation chips.

Architecture (AnthroKit-Hiring):
  anthrokit_hiring.yaml  ->  LowA / HighA token spec (self_reference, warmth,
                             formality, empathy, hedging)
  anthrokit_prompts.py   ->  pre-authored pattern cards for constrained input paths
                             (named priorities, named Stage 2 challenge keywords)
  anthrokit_stylizer.py  ->  load_preset(); generate_grounded_response() for the
                             two open-ended HIC paths where cards cannot exist
  renderer.py            ->  this file — orchestration only; no inline text

Two input paths require LLM generation rather than static cards, because the
recruiter input is open-ended and cards cannot be pre-authored for every value:
  1. Free-text recruiter notes in Stage 1 HIC steering (_steered_text)
  2. Novel Stage 2 challenges outside the 7 named keyword categories (_render_custom_fallback)

All other paths (named priorities, named challenges, non-HIC Stage 1) use static cards.
"""

from __future__ import annotations

from .conditions import Condition
from .evidence_store import EvidenceStore
from .retriever import EvidenceRetriever
from .schemas import CandidateEvaluation, EvidenceSection, RenderedResponse
from .anthrokit_prompts import (
    card_main_recommendation,
    card_support_evidence,
    card_caution_evidence,
    card_uncertain_requirements,
    card_missing_information,
    card_strict_policy,
    card_transferable_weight,
    card_growth_potential,
    card_priority_evidence,
    PRIORITY_STRENGTH,
    prose,
)
from .anthrokit_stylizer import generate_grounded_response, load_preset


class RecommendationRenderer:
    def __init__(self, evidence_store: EvidenceStore) -> None:
        self.store = evidence_store
        self.retriever = EvidenceRetriever(evidence_store)

    def render(
        self,
        recommendation: str,
        evaluation: CandidateEvaluation,
        condition: Condition,
        user_priorities: list[str],
        user_notes: str = "",
    ) -> RenderedResponse:
        chips = (
            self.retriever.retrieve_citation_chips()
            if condition.explainability
            else []
        )
        text = self._build_text(
            recommendation, evaluation, condition, user_priorities, user_notes
        )
        return RenderedResponse(text=text, citation_chips=chips)

    def _build_text(
        self,
        recommendation: str,
        evaluation: CandidateEvaluation,
        condition: Condition,
        user_priorities: list[str],
        user_notes: str = "",
    ) -> str:
        has_steering = condition.hic and (user_priorities or user_notes.strip())
        if has_steering:
            return self._steered_text(recommendation, condition, user_priorities, user_notes)
        return card_main_recommendation(
            high_e=condition.explainability,
            high_a=condition.anthropomorphic_cues,
            recommendation=recommendation,
        )

    def _steered_text(
        self,
        recommendation: str,
        condition: Condition,
        user_priorities: list[str],
        user_notes: str,
    ) -> str:
        """Build a steered recommendation narrative from recruiter priorities.

        Structure: opener -> priority evidence blocks -> evidence-adaptive closer.
        Register follows anthrokit_hiring.yaml LowA / HighA presets.
        All block text is delegated to card_priority_evidence() in anthrokit_prompts.py.
        """
        prose_rec = prose(recommendation)
        named = [p for p in user_priorities if p != "Other concern"]

        # ── Opener (A-sensitive) ──────────────────────────────────────────────
        if condition.anthropomorphic_cues:
            if named:
                area_list = ", ".join(named)
                opener = (
                    f"You asked me to focus on {area_list} - "
                    "so here is what I found on each of those. "
                )
            else:
                opener = (
                    "You asked me to review the candidate with your notes in mind - "
                    "here is what I found. "
                )
        else:
            if named:
                area_list = ", ".join(named)
                opener = f"Assessment re-weighted per reviewer priorities: {area_list}.\n\n"
            else:
                opener = "Assessment incorporating reviewer notes.\n\n"

        # ── Priority evidence blocks (delegated to anthrokit_prompts card) ────
        blocks: list[str] = []
        for priority in named:
            block = card_priority_evidence(
                priority,
                high_e=condition.explainability,
                high_a=condition.anthropomorphic_cues,
            )
            if block:
                blocks.append(block)

        # ── Free-text note: LLM-generated, A-register applied via token spec ────
        # This is the one path where pre-authored cards cannot exist — the input
        # is open-ended. generate_grounded_response() applies the full AnthroKit
        # token spec (warmth, formality, empathy, hedging, self_reference) in a
        # single deterministic LLM call. temperature=0 + seed → same output for
        # all participants in the same condition who enter the same note.
        if user_notes.strip():
            relevant = self.store.search(user_notes.strip(), top_k=2)
            evidence_summary = "; ".join(
                f"{s.heading}: {s.text[:180].rstrip()}..."
                if len(s.text) > 180
                else f"{s.heading}: {s.text}"
                for s in relevant
            ) if relevant else ""
            preset = load_preset(int(condition.anthropomorphic_cues))
            blocks.append(
                generate_grounded_response(user_notes.strip(), evidence_summary, preset)
            )

        # ── Closer: evidence-adaptive, recruiter authority foregrounded ───────
        uncertain = [p for p in named if PRIORITY_STRENGTH.get(p) == "uncertain"]
        strong = [p for p in named if PRIORITY_STRENGTH.get(p) == "strong"]
        is_hold = recommendation == "Hold for further review"

        if condition.anthropomorphic_cues:
            if is_hold:
                gap_list = ", ".join(uncertain)
                closer = (
                    f"Based on what you focused on, my recommendation is to {prose_rec}. "
                    f"You flagged {gap_list} - and that is precisely where the CV does not "
                    "give me enough to work with. This is not a rejection; it means the "
                    "materials available are not sufficient to satisfy the priorities you set. "
                    "The call is yours to make."
                )
            elif uncertain:
                gap_list = ", ".join(uncertain)
                strong_note = (
                    f" The case is stronger on {', '.join(strong)}." if strong else ""
                )
                closer = (
                    f"Based on those priorities, my recommendation is to {prose_rec} - "
                    f"but I want to be direct: {gap_list} is the part I cannot resolve "
                    f"from the CV alone.{strong_note} "
                    "I would advance, but design the interview specifically to test that gap. "
                    "The decision is yours."
                )
            elif strong:
                strong_list = ", ".join(strong)
                closer = (
                    f"Based on those priorities, my recommendation is to {prose_rec}. "
                    f"The areas you focused on - {strong_list} - are all well evidenced. "
                    "That is a solid basis for the next stage. The call is yours."
                )
            else:
                closer = (
                    f"Based on those priorities, my recommendation is to {prose_rec}. "
                    "You have seen what the evidence shows on the areas you care about. "
                    "The decision is yours to make."
                )
        else:
            if is_hold:
                gap_list = ", ".join(uncertain)
                closer = (
                    f"Outcome: {prose_rec}. "
                    f"Insufficient evidence for reviewer-flagged areas: {gap_list}. "
                    "Further evidence required before progression. "
                    "Final determination: recruiter discretion."
                )
            elif uncertain:
                gap_list = ", ".join(uncertain)
                closer = (
                    f"Outcome: {prose_rec}. "
                    f"Evidence gap identified: {gap_list}. "
                    "Interview to specifically assess flagged areas. "
                    "Final determination: recruiter discretion."
                )
            else:
                closer = (
                    f"Outcome: {prose_rec}. "
                    "Reviewer-prioritised areas assessed and evidenced. "
                    "Final determination: recruiter discretion."
                )

        if condition.anthropomorphic_cues:
            body = " ".join(blocks)
            return opener + body + (" " + closer if body else closer)
        body = "\n\n".join(blocks)
        return opener + body + ("\n\n" + closer if body else closer)

    # ── Stage 2 challenge responses ───────────────────────────────────────────

    def render_challenge_response(
        self,
        challenge: str,
        evidence: list[EvidenceSection],
        condition: Condition,
        current_recommendation: str = "Advance to human interview",
    ) -> str:
        """Dispatch Stage 2 challenge to the appropriate anthrokit_prompts card."""
        high_e = condition.explainability
        high_a = condition.anthropomorphic_cues
        challenge_l = challenge.lower()

        if (
            "supporting" in challenge_l
            or "advance" in challenge_l
            or "progression" in challenge_l
        ):
            base = card_support_evidence(high_e, high_a)
        elif "caution" in challenge_l or "concern" in challenge_l:
            base = card_caution_evidence(high_e, high_a)
        elif (
            "uncertain" in challenge_l
            or "unmet" in challenge_l
            or "requirements" in challenge_l
        ):
            base = card_uncertain_requirements(high_e, high_a)
        elif "missing" in challenge_l:
            base = card_missing_information(high_e, high_a)
        elif "strict" in challenge_l:
            base = card_strict_policy(high_e, high_a)
        elif "growth" in challenge_l or "potential" in challenge_l:
            base = card_growth_potential(high_e, high_a)
        elif "transferable" in challenge_l:
            base = card_transferable_weight(high_e, high_a)
        else:
            fallback = self._render_custom_fallback(challenge, evidence, condition)
            return fallback + self._standing_recommendation_note(
                current_recommendation, condition
            )

        grounded = self._append_evidence_grounding(base, evidence, condition)
        return grounded + self._standing_recommendation_note(
            current_recommendation, condition
        )

    @staticmethod
    def _standing_recommendation_note(recommendation: str, condition: Condition) -> str:
        """Brief standing-recommendation anchor appended after a Stage 2 response."""
        is_hold = recommendation == "Hold for further review"
        if condition.anthropomorphic_cues:
            if is_hold:
                return "\n\nMy recommendation remains: hold for further review."
            return (
                "\n\nThis does not change my recommendation to advance - "
                "but it clarifies what to test at interview."
            )
        if is_hold:
            return "\n\nStanding recommendation: Hold for further review."
        return "\n\nStanding recommendation: Advance to human interview."

    def _append_evidence_grounding(
        self,
        base: str,
        evidence: list[EvidenceSection],
        condition: Condition,
    ) -> str:
        """For E=1 conditions: append retrieved section labels to the card text."""
        if not condition.explainability or not evidence:
            return base
        role_labels = [
            e.section_label for e in evidence if e.document_key == "role_description"
        ][:2]
        policy_labels = [
            e.section_label for e in evidence if e.document_key == "screening_policy"
        ][:2]
        cv_labels = [
            e.section_label for e in evidence if e.document_key == "candidate_cv"
        ][:1]
        parts: list[str] = []
        if role_labels:
            parts.append(f"Role Description: {', '.join(role_labels)}")
        if policy_labels:
            parts.append(f"Screening Policy: {', '.join(policy_labels)}")
        if cv_labels:
            parts.append(f"Candidate CV: {', '.join(cv_labels)}")
        if not parts:
            return base
        sourced = "; ".join(parts)
        if condition.anthropomorphic_cues:
            return base + f"\n\n*(Retrieved sections used: {sourced}.)*"
        return base + f"\n\nRetrieved sections: {sourced}."

    def _render_custom_fallback(
        self,
        challenge: str,
        evidence: list[EvidenceSection],
        condition: Condition,
    ) -> str:
        """Respond to a novel Stage 2 challenge using retrieved evidence sections.

        This is the second open-ended path where pre-authored cards cannot exist —
        the recruiter has typed a challenge outside the 7 named keyword categories.
        generate_grounded_response() applies the full AnthroKit token spec in a
        single deterministic LLM call, grounded in the retrieved evidence sections.
        """
        if condition.explainability and evidence:
            section_list = "; ".join(
                f"{s.section_label} ({s.document_title})" for s in evidence[:2]
            )
            evidence_summary = section_list
        elif evidence:
            evidence_summary = "; ".join(
                f"{s.heading}: {s.text[:160].rstrip()}..." if len(s.text) > 160
                else f"{s.heading}: {s.text}"
                for s in evidence[:2]
            )
        else:
            evidence_summary = ""

        preset = load_preset(int(condition.anthropomorphic_cues))
        return generate_grounded_response(challenge, evidence_summary, preset)
