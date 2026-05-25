"""Recommendation renderer.

Produces condition-appropriate text and citation chips.  The only variables
are explainability, anthropomorphic cues, and whether Stage 1 user priorities
are present.  The underlying evidence and recommendation are constant.
"""

from __future__ import annotations

from .conditions import Condition
from .evidence_store import EvidenceStore
from .retriever import EvidenceRetriever
from .schemas import CandidateEvaluation, EvidenceSection, RenderedResponse

# ── Stage 2 challenge response templates ──────────────────────────────────────

_SUPPORTING_EVIDENCE_RESPONSE = {
    "low_e_low_a": (
        "The strongest supporting evidence is the candidate's coordination and applicant "
        "tracking work in the current role, along with demonstrated stakeholder communication. "
        "These align with the role's process coordination and communication requirements."
    ),
    "low_e_high_a": (
        "Looking at what most supports moving this candidate forward: the hands-on "
        "coordination, scheduling, and tracking work is genuinely relevant here. The "
        "candidate has been working directly with hiring managers and applicants — "
        "that's not nothing, and it maps reasonably well to what the role needs."
    ),
    "high_e_low_a": (
        "The strongest supporting evidence is the applicant coordination, tracking, and "
        "hiring manager communication documented in the current BrightScale role (cv_1). "
        "This aligns with Section 5.2 (Process Coordination) and Section 5.5 (Stakeholder "
        "Management) of the role description. The screening policy's transferable evidence "
        "clause (Section 7.2) additionally supports progression where direct title "
        "equivalence is absent."
    ),
    "high_e_high_a": (
        "What most supports moving this candidate forward is the current BrightScale role "
        "— specifically the candidate scheduling, tracking sheet maintenance, and "
        "communication across hiring managers and applicants. That maps directly to "
        "Section 5.2 and Section 5.5. And importantly, the screening policy explicitly "
        "says that where the exact wording isn't there but the underlying capability is "
        "demonstrated, that can still count — Section 7.2 makes that clear."
    ),
}

_CAUTION_EVIDENCE_RESPONSE = {
    "low_e_low_a": (
        "The main caution is that the CV does not clearly demonstrate end-to-end "
        "recruitment ownership or independent screening decision authority. These "
        "are preferred or required capabilities that are not fully evidenced."
    ),
    "low_e_high_a": (
        "The thing that gives me the most pause is that the CV doesn't clearly show "
        "the candidate owning a recruitment process end-to-end, or making independent "
        "screening decisions. That's worth keeping in mind — it's a real gap in the evidence."
    ),
    "high_e_low_a": (
        "The strongest caution evidence relates to Section 5.4 (Structured Evaluation "
        "Support): the CV does not clearly demonstrate independent evaluation authority "
        "or end-to-end screening ownership. Section 6.2 identifies direct talent "
        "operations or recruitment coordination as a preferred qualification, which "
        "the candidate has not held under a formal title."
    ),
    "high_e_high_a": (
        "The strongest reason for caution is what's not clearly shown: Section 5.4 "
        "requires evidence of structured evaluation support, and the CV doesn't "
        "demonstrate independent decision authority over screening outcomes. "
        "Section 6.2 also identifies direct talent operations experience as "
        "preferred — and the candidate hasn't worked under that kind of title. "
        "These are real gaps, not just wording issues."
    ),
}

_UNCERTAIN_REQUIREMENTS_RESPONSE = {
    "low_e_low_a": (
        "Requirements that remain uncertain: direct end-to-end talent screening "
        "ownership; independent evaluation decision authority; experience holding "
        "a formal recruitment or talent operations title."
    ),
    "low_e_high_a": (
        "The main things I'm still not sure about are whether the candidate has "
        "genuinely owned a recruitment process from start to finish, and whether "
        "they've made independent screening decisions rather than supporting someone "
        "else who made those calls."
    ),
    "high_e_low_a": (
        "The following requirements remain uncertain based on the available evidence. "
        "Section 5.4 (Structured Evaluation Support): the CV indicates support work "
        "but does not clearly establish independent decision authority. Section 6.2 "
        "(Direct Talent Operations): no formal recruitment title has been held. "
        "Section 5.6 (Independent Execution): the SME context is present but "
        "autonomous decision ownership is not clearly documented."
    ),
    "high_e_high_a": (
        "After going through the evidence, the things I'm genuinely uncertain about "
        "are: Section 5.4 — it's not clear the candidate has owned evaluation "
        "decisions rather than supported them; and Section 6.2 — the preferred "
        "direct talent operations experience isn't there under a formal title. "
        "Section 5.6 is partially satisfied but not fully established either. "
        "These aren't disqualifying gaps, but they are real unknowns."
    ),
}

_MISSING_INFORMATION_RESPONSE = {
    "low_e_low_a": (
        "Information that is missing: explicit documentation of end-to-end "
        "recruitment process ownership; evidence of independent screening "
        "decisions; clarification of whether past evaluation work was independent "
        "or under supervision."
    ),
    "low_e_high_a": (
        "What's missing is mostly clarity about the candidate's actual authority "
        "in past roles. Did they own the screening process, or support someone "
        "else who did? That distinction matters here and the CV doesn't answer it."
    ),
    "high_e_low_a": (
        "Information absent from the available materials includes: explicit "
        "documentation of end-to-end recruitment or screening process ownership; "
        "evidence distinguishing the candidate's independent decision authority "
        "from supervised support work; any clarification of scope in the Nexa "
        "shortlisting work (cv_2). Interview would allow direct examination "
        "of these points."
    ),
    "high_e_high_a": (
        "The main thing the CV doesn't tell us is how much of the past work "
        "was the candidate's own call versus supporting someone else's decision. "
        "That matters for Section 5.4 and Section 6.2 — which both care about "
        "independent judgement and ownership. Interview would be the natural "
        "place to explore that."
    ),
}

_STRICTER_POLICY_RESPONSE = {
    "low_e_low_a": (
        "Under a stricter policy interpretation, the absence of direct end-to-end "
        "recruitment ownership and independent screening authority would weigh "
        "more heavily. A stricter reading would favour Hold for Further Review "
        "given the material uncertainty across key requirements."
    ),
    "low_e_high_a": (
        "If I apply the policy more strictly, the picture changes a bit. "
        "The gaps around independent decision authority and direct recruitment "
        "ownership become harder to set aside. Under a stricter reading, "
        "holding the candidate for further review would be reasonable."
    ),
    "high_e_low_a": (
        "Under a stricter policy interpretation, Section 6.4 (Hold for Further "
        "Review) becomes the more appropriate outcome. Where meaningful strengths "
        "coexist with unresolved gaps, the policy supports further review rather "
        "than automatic progression. The absence of direct evidence for Section 5.4 "
        "and Section 6.2 would carry greater weight under strict application."
    ),
    "high_e_high_a": (
        "Under a stricter reading of the policy, I would lean more toward holding "
        "than advancing. Section 6.4 says that where there's plausible fit but "
        "material uncertainty, hold is the right call — and the gaps around "
        "Section 5.4 and Section 6.2 are real. The candidate isn't clearly "
        "unsuitable, but a strict reading would say the uncertainty warrants "
        "more review before progression."
    ),
}

_TRANSFERABLE_WEIGHT_RESPONSE = {
    "low_e_low_a": (
        "With greater weight on transferable evidence, the candidate's coordination, "
        "tracking, and stakeholder communication work across multiple roles provides "
        "credible evidence of underlying talent operations capability. "
        "The recommendation to advance is reinforced."
    ),
    "low_e_high_a": (
        "If I give more credit to the transferable evidence, the case for "
        "progressing this candidate gets stronger. The coordination, follow-up, "
        "and applicant-facing work across roles shows real capability — it just "
        "hasn't been done under a formal recruitment title."
    ),
    "high_e_low_a": (
        "With greater weight on transferable evidence, the policy's Section 7.2 "
        "and Section 7.3 become more significant. Section 7.3 prohibits rejection "
        "on keyword grounds alone, and Section 7.2 allows adjacent experience to "
        "satisfy required qualifications. The candidate's coordination, tracking, "
        "and screening-support work (cv_1, cv_2) constitutes credible transferable "
        "evidence for the core required qualifications."
    ),
    "high_e_high_a": (
        "When I give more weight to the transferable evidence, the candidate "
        "looks more clearly progression-ready. Section 7.3 says you can't reject "
        "someone just because they don't use the exact wording, and Section 7.2 "
        "says adjacent experience can satisfy requirements. The coordination, "
        "tracking, and applicant communication work is the kind of thing the "
        "policy is designed to credit — even without a formal recruitment title."
    ),
}


# ── Main renderer ─────────────────────────────────────────────────────────────

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
    ) -> RenderedResponse:
        chips = (
            self.retriever.retrieve_citation_chips()
            if condition.explainability
            else []
        )
        text = self._build_text(recommendation, evaluation, condition, user_priorities)
        return RenderedResponse(text=text, citation_chips=chips)

    def _build_text(
        self,
        recommendation: str,
        evaluation: CandidateEvaluation,
        condition: Condition,
        user_priorities: list[str],
    ) -> str:
        focus_prefix = ""
        if condition.mixed_initiative_control_cues and user_priorities:
            areas = ", ".join(user_priorities)
            if condition.anthropomorphic_cues:
                focus_prefix = (
                    f"You asked me to pay particular attention to {areas}. "
                    "I have kept those priorities in mind in my review below. "
                )
            else:
                focus_prefix = (
                    f"This assessment incorporates the user-specified "
                    f"priorities: {areas}. "
                )

        if not condition.explainability and not condition.anthropomorphic_cues:
            return focus_prefix + self._low_e_low_a(recommendation)
        if not condition.explainability and condition.anthropomorphic_cues:
            return focus_prefix + self._low_e_high_a(recommendation)
        if condition.explainability and not condition.anthropomorphic_cues:
            return focus_prefix + self._high_e_low_a(recommendation)
        return focus_prefix + self._high_e_high_a(recommendation)

    @staticmethod
    def _low_e_low_a(recommendation: str) -> str:
        return (
            f"The assessment outcome is to {recommendation.lower()} this candidate. "
            "The CV shows evidence of process coordination, applicant tracking, and "
            "stakeholder communication that aligns with the role's core requirements. "
            "Some requirements are only partially evidenced, which may be worth "
            "exploring at interview."
        )

    @staticmethod
    def _low_e_high_a(recommendation: str) -> str:
        return (
            "After reviewing the candidate's materials, I would recommend to "
            f"{recommendation.lower()} this candidate. "
            "There are useful signs of coordination experience and the ability to work "
            "across stakeholders — which is relevant here. Some areas would benefit "
            "from closer examination at interview, but the overall picture seems "
            "sufficient to continue the process."
        )

    @staticmethod
    def _high_e_low_a(recommendation: str) -> str:
        return (
            "Based on the available materials, the assessment outcome is to "
            f"{recommendation.lower()} this candidate. "
            "The CV demonstrates evidence of process coordination (Section 5.2) and "
            "stakeholder management (Section 5.5) that aligns with the role's required "
            "capabilities. Evidence of structured evaluation support is present but "
            "does not clearly establish independent decision authority (Section 5.4). "
            "The screening policy allows transferable evidence to satisfy required "
            "qualifications where direct wording is absent (Sections 7.2 and 7.3). "
            "The candidate's coordination work constitutes credible transferable "
            "evidence for the primary required capabilities. The main remaining "
            "uncertainty — direct end-to-end recruitment ownership — is best examined "
            "at interview rather than treated as grounds for exclusion at this stage."
        )

    @staticmethod
    def _high_e_high_a(recommendation: str) -> str:
        return (
            "After reviewing the CV, I would recommend to "
            f"{recommendation.lower()} this candidate. "
            "What stands out most is the coordination experience: scheduling, applicant "
            "tracking, and communication across hiring managers and applicants, which "
            "maps closely to Section 5.2 and Section 5.5 of the role description. "
            "The part that gives me some hesitation is that the CV does not clearly "
            "show ownership of end-to-end recruitment screening, which Section 5.4 "
            "identifies as a key area. That said, the screening policy specifically "
            "says that transferable evidence can count where equivalent capability is "
            "visible, even without exact wording — see Sections 7.2 and 7.3. "
            "Given the coordination strengths and the policy support for transferable "
            "evidence, I think this candidate merits interview progression rather than "
            "screening out at this stage."
        )

    # ── Stage 2 challenge responses ───────────────────────────────────────────

    def render_challenge_response(
        self,
        challenge: str,
        evidence: list[EvidenceSection],
        condition: Condition,
    ) -> str:
        key = self._condition_key(condition)

        if "strongest evidence supporting" in challenge.lower() or "strongest reason to advance" in challenge.lower():
            return _SUPPORTING_EVIDENCE_RESPONSE[key]
        if "caution" in challenge.lower() or "against" in challenge.lower():
            return _CAUTION_EVIDENCE_RESPONSE[key]
        if "uncertain" in challenge.lower():
            return _UNCERTAIN_REQUIREMENTS_RESPONSE[key]
        if "missing" in challenge.lower():
            return _MISSING_INFORMATION_RESPONSE[key]
        if "stricter" in challenge.lower():
            return _STRICTER_POLICY_RESPONSE[key]
        if "transferable" in challenge.lower():
            return _TRANSFERABLE_WEIGHT_RESPONSE[key]
        # Custom question fallback
        if condition.anthropomorphic_cues:
            return (
                "That's a fair question. My assessment is based on the materials "
                "available — the role description, screening policy, company context, "
                "and the candidate CV. I can only respond to what's documented. "
                "If your question relates to something outside those materials, "
                "it would need to be explored directly with the candidate."
            )
        return (
            "The assessment is grounded in the role description, screening policy, "
            "company context, and candidate CV. Questions beyond the scope of "
            "those materials cannot be addressed within this system."
        )

    @staticmethod
    def _condition_key(condition: Condition) -> str:
        e = "high_e" if condition.explainability else "low_e"
        a = "high_a" if condition.anthropomorphic_cues else "low_a"
        return f"{e}_{a}"
