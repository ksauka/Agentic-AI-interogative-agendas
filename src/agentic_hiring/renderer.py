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

_GROWTH_POTENTIAL_RESPONSE = {
    "low_e_low_a": (
        "The candidate's trajectory from project support to people coordination roles "
        "demonstrates increasing scope and responsibility over time. Growth potential "
        "is consistent with the role's expected learning curve and what the screening "
        "policy allows to be considered at this stage."
    ),
    "low_e_high_a": (
        "The trajectory here is worth considering. The candidate has moved from project "
        "support to coordinating across hiring cycles — that progression suggests someone "
        "who builds responsibility over time. It doesn't answer every question about the "
        "role, but it's a meaningful signal that points toward interview rather than exclusion."
    ),
    "high_e_low_a": (
        "Growth potential is addressed by the screening policy's Adjacent Experience Rule "
        "(Section 7.4), which supports candidates demonstrating increasing scope in "
        "adjacent roles rather than holding a direct title. The candidate's progression "
        "from client support at Nexa (cv_2) to talent operations coordination at "
        "BrightScale (cv_1) fits that pattern. This does not resolve the uncertainty "
        "around Section 5.4, but it is consistent with a trajectory toward the role "
        "and supports progression to interview where growth can be examined directly."
    ),
    "high_e_high_a": (
        "On growth potential: Section 7.4 — the Adjacent Experience Rule — is directly "
        "relevant here. The policy supports candidates who have been building toward the "
        "role, not just those who've already held the title. The trajectory from client "
        "support at Nexa to talent operations coordination at BrightScale is consistent "
        "with that pathway. It doesn't resolve the Section 5.4 uncertainty, but it "
        "adds genuine weight to advancing rather than holding at this stage."
    ),
}


# ── Priority-specific commentary (Stage 1 steering, C=1) ─────────────────────
# Maps each FOCUS_AREA to (neutral text, warm text, role refs, policy refs).
# Woven into the recommendation body when the user has selected priorities.

_PRIORITY_COMMENTARY: dict[str, dict] = {
    "Independent ownership": {
        "low_a": (
            "On independent ownership: the CV documents coordination and support activities "
            "but does not clearly establish autonomous decision authority over screening "
            "outcomes. This remains the principal gap in the evidence."
        ),
        "high_a": (
            "On the independence question specifically: what the CV shows is coordination "
            "and support work — but it is not clear whether the candidate owned the final "
            "calls or was implementing someone else's decisions. That distinction is worth "
            "testing directly at interview."
        ),
        "role_refs": ["Section 5.4", "Section 5.6"],
        "policy_refs": [],
    },
    "Stakeholder communication": {
        "low_a": (
            "On stakeholder communication: the CV documents structured "
            "coordination across hiring managers, applicants, and leadership. This is "
            "one of the better-evidenced areas of the application."
        ),
        "high_a": (
            "Looking at stakeholder communication specifically: this is "
            "genuinely one of the stronger areas of the CV. The candidate has been working "
            "directly across hiring managers, candidates, and leadership — that maps well "
            "to what the role requires."
        ),
        "role_refs": ["Section 5.3", "Section 5.5"],
        "policy_refs": [],
    },
    "Transferable experience": {
        "low_a": (
            "On transferable experience: the coordination and evaluation-support work "
            "across both roles provides credible adjacent evidence for the primary required "
            "capabilities. The policy's transferability rules support this interpretation."
        ),
        "high_a": (
            "On transferable experience: what I see here is someone who has been doing the "
            "practical work of recruitment support without the formal title. The policy is "
            "explicit that this kind of evidence should count — that is directly relevant "
            "to how the recommendation has been framed."
        ),
        "role_refs": [],
        "policy_refs": ["Section 7.2", "Section 7.3"],
    },
    "Structured evaluation or screening experience": {
        "low_a": (
            "On structured evaluation or screening experience: the CV evidences participation in "
            "structured interview preparation, candidate tracking, and evaluation-adjacent "
            "activities. End-to-end independent screening ownership is not clearly demonstrated."
        ),
        "high_a": (
            "On structured evaluation or screening experience: there is real participation in those "
            "processes — interview pack preparation, candidate tracking, structured follow-up. "
            "What is less clear is whether the candidate owned the screening decisions or was "
            "supporting someone who did. That is the core remaining question."
        ),
        "role_refs": ["Section 5.4"],
        "policy_refs": [],
    },
    "Operational coordination": {
        "low_a": (
            "On operational coordination: the CV demonstrates consistent structured tracking, "
            "multi-stage follow-up, and cross-team communication across both roles. This is "
            "the most consistently evidenced area of the application."
        ),
        "high_a": (
            "The coordination evidence is genuinely the strongest part of this application — "
            "structured tracking, staged follow-up, cross-team communication, consistently "
            "across two different employers. That gives a solid basis for the core operational "
            "capability."
        ),
        "role_refs": ["Section 5.2"],
        "policy_refs": [],
    },
    "Growth potential": {
        "low_a": (
            "On growth potential: the CV shows progression from project support to "
            "coordination roles with increasing cross-functional scope. This trajectory "
            "is relevant but harder to assess directly against the screening criteria."
        ),
        "high_a": (
            "On growth potential: the trajectory here — from project support to coordinating "
            "across full hiring cycles — suggests someone who has taken on more responsibility "
            "over time. That is harder to assess directly against the criteria, but it is "
            "a meaningful signal."
        ),
        "role_refs": [],
        "policy_refs": [],
    },
}


# ── Per-priority evidence blocks (Stage 1 MICC steering) ─────────────────────
# Keyed by focus_area → condition_key → paragraph.
# Each paragraph addresses the priority with grounded section references (high-E)
# or plain summary language (low-E).

_PRIORITY_EVIDENCE: dict[str, dict[str, str]] = {
    "Independent ownership": {
        "high_e_low_a": (
            "On independent ownership (Section 5.4, Section 5.6): the CV documents process "
            "support and scheduling work, but does not clearly establish independent "
            "decision authority over candidate outcomes or end-to-end screening ownership. "
            "Section 7.2 provides that this gap should be examined at interview rather "
            "than treated as a basis for exclusion at screening stage."
        ),
        "high_e_high_a": (
            "You asked about independent ownership — and that's where the CV is least "
            "clear. Section 5.4 and Section 5.6 both ask for evidence of owning decisions "
            "independently, and the CV shows support work rather than ownership. That said, "
            "Section 7.2 says this kind of gap should be examined at interview, not used "
            "to screen someone out. So it's a flag, not a disqualifier."
        ),
        "low_e_low_a": (
            "On independent ownership: the CV does not clearly demonstrate independent "
            "decision authority over screening outcomes. This is the main evidence gap."
        ),
        "low_e_high_a": (
            "On independent ownership: this is where the evidence is thinnest. "
            "The candidate has supported decisions but the CV doesn't show them "
            "owning the call. Worth keeping in mind."
        ),
    },
    "Stakeholder communication": {
        "high_e_low_a": (
            "On stakeholder communication (Section 5.3, Section 5.5): the CV "
            "directly documents communication across hiring managers and applicants in the "
            "BrightScale role. Both requirements are credibly evidenced and constitute a "
            "material strength in the candidate's profile."
        ),
        "high_e_high_a": (
            "On stakeholder communication: this is one of the clearest "
            "strengths. The BrightScale role involves direct communication across hiring "
            "managers and applicants — Section 5.3 and Section 5.5 are both addressed. "
            "This is credible evidence, not inferential."
        ),
        "low_e_low_a": (
            "On stakeholder communication: direct communication across "
            "hiring managers and applicants is documented in the CV. This requirement "
            "is clearly evidenced."
        ),
        "low_e_high_a": (
            "On stakeholder communication: this is where the candidate "
            "looks strongest. Cross-team communication is clearly documented and is "
            "directly relevant to what the role needs."
        ),
    },
    "Transferable experience": {
        "high_e_low_a": (
            "On transferable experience (Section 7.2, Section 7.3, Section 7.4): the screening policy "
            "explicitly prohibits exact-match rejection and provides that adjacent experience "
            "satisfies required qualifications where equivalent capability is visible. The "
            "candidate's coordination, tracking, and applicant-facing work constitutes "
            "credible transferable evidence for the core required capabilities."
        ),
        "high_e_high_a": (
            "On transferable experience: the policy is clear here. Section 7.3 says you "
            "can't reject someone for not using the exact words, and Section 7.2 says "
            "adjacent experience counts where the underlying capability is visible. The "
            "candidate's work — even without the formal title — is the kind of thing "
            "the policy is designed to credit."
        ),
        "low_e_low_a": (
            "On transferable experience: the screening policy supports crediting adjacent "
            "coordination and screening-support work where direct title equivalence is absent."
        ),
        "low_e_high_a": (
            "On transferable experience: there's policy support here. The work isn't a "
            "perfect match on paper, but the policy is clear that's not the right test — "
            "the underlying capability is what matters."
        ),
    },
    "Structured evaluation or screening experience": {
        "high_e_low_a": (
            "On structured evaluation or screening experience (Section 5.4): the CV documents "
            "applicant tracking, scheduling, and shortlisting support across two roles. "
            "Section 5.4 requires structured evaluation support — this is partially "
            "evidenced. Independent decision authority over screening outcomes is not "
            "clearly established and is the primary remaining uncertainty."
        ),
        "high_e_high_a": (
            "On structured evaluation or screening experience: there's tracking and shortlisting "
            "support in the CV, which addresses part of Section 5.4. The part that's "
            "less clear is whether the candidate was making decisions or supporting "
            "someone else's decisions. That distinction is what I can't resolve from "
            "the CV alone."
        ),
        "low_e_low_a": (
            "On structured evaluation or screening experience: tracking and shortlisting support "
            "is documented. Independent decision authority over screening outcomes "
            "is not clearly established."
        ),
        "low_e_high_a": (
            "On structured evaluation or screening experience: the candidate has done screening "
            "support work, but the CV isn't clear on whether they were making the calls "
            "or supporting someone else who was. That's the main thing to look at here."
        ),
    },
    "Operational coordination": {
        "high_e_low_a": (
            "On operational coordination (Section 5.2): this is the candidate's most "
            "clearly evidenced required capability. The BrightScale role directly "
            "documents scheduling, tracking sheet maintenance, and cross-functional "
            "follow-up — all of which map to the process coordination requirement."
        ),
        "high_e_high_a": (
            "On operational coordination: this is the strongest part of the profile. "
            "Section 5.2 asks for process coordination, and the BrightScale role is "
            "exactly that — scheduling, tracking, following up across teams. "
            "Clearly and directly evidenced."
        ),
        "low_e_low_a": (
            "On operational coordination: process coordination, scheduling, and tracking "
            "are clearly documented in the CV. This is the most strongly evidenced "
            "required capability."
        ),
        "low_e_high_a": (
            "On operational coordination: this is where the candidate is most clearly "
            "strong. The scheduling and tracking work maps directly to what the role needs."
        ),
    },
    "Growth potential": {
        "high_e_low_a": (
            "On growth potential (Section 7.4): the screening policy's Adjacent Experience "
            "Rule supports crediting candidates operating in adjacent roles at increasing "
            "levels of responsibility. The candidate's progression toward talent operations "
            "work is structurally supported by the policy framework."
        ),
        "high_e_high_a": (
            "On growth potential: Section 7.4 — the Adjacent Experience Rule — is "
            "relevant here. The policy supports candidates who have been building toward "
            "the role rather than holding the exact title. The trajectory matters, "
            "not just the current label."
        ),
        "low_e_low_a": (
            "On growth potential: the screening policy supports adjacent experience "
            "at increasing levels of responsibility as a qualifying pathway."
        ),
        "low_e_high_a": (
            "On growth potential: the policy does support this kind of trajectory. "
            "It's not just about the current role — progression toward the work counts."
        ),
    },
}


# ── Recommendation → grammatical verb phrase ──────────────────────────────────

_PROSE_PHRASE: dict[str, str] = {
    "Advance to human interview": "advance this candidate to a human interview",
    "Hold for further review": "hold this candidate for further review",
    "Reject application": "reject this application",
}

_PROSE_GERUND: dict[str, str] = {
    "Advance to human interview": "advancing this candidate to a human interview",
    "Hold for further review": "holding this candidate for further review",
    "Reject application": "rejecting this application",
}


def _prose(recommendation: str) -> str:
    return _PROSE_PHRASE.get(recommendation, recommendation.lower())


def _prose_gerund(recommendation: str) -> str:
    return _PROSE_GERUND.get(recommendation, recommendation.lower())


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
        user_notes: str = "",
    ) -> RenderedResponse:
        chips = (
            self.retriever.retrieve_citation_chips()
            if condition.explainability
            else []
        )
        text = self._build_text(recommendation, evaluation, condition, user_priorities, user_notes)
        return RenderedResponse(text=text, citation_chips=chips)

    def _build_text(
        self,
        recommendation: str,
        evaluation: CandidateEvaluation,
        condition: Condition,
        user_priorities: list[str],
        user_notes: str = "",
    ) -> str:
        has_steering = condition.hic and (
            user_priorities or user_notes.strip()
        )
        if has_steering:
            return self._steered_text(recommendation, condition, user_priorities, user_notes)

        # No steering — fall through to static condition templates
        if not condition.explainability and not condition.anthropomorphic_cues:
            return self._low_e_low_a(recommendation)
        if not condition.explainability and condition.anthropomorphic_cues:
            return self._low_e_high_a(recommendation)
        if condition.explainability and not condition.anthropomorphic_cues:
            return self._high_e_low_a(recommendation)
        return self._high_e_high_a(recommendation)

    def _steered_text(
        self,
        recommendation: str,
        condition: Condition,
        user_priorities: list[str],
        user_notes: str,
    ) -> str:
        """Build a recommendation narrative that genuinely addresses the user's selected priorities."""
        key = self._condition_key(condition)
        prose_rec = _prose(recommendation)

        # ── Opening ──────────────────────────────────────────────────────────
        named = [p for p in user_priorities if p != "Other concern"]
        if condition.anthropomorphic_cues:
            if named:
                area_list = ", ".join(named)
                opener = (
                    f"I reviewed the candidate with your priorities in mind — "
                    f"{area_list}. "
                    f"My recommendation is to {prose_rec}. "
                    "Here is what I found on each of those areas:\n\n"
                )
            else:
                opener = (
                    f"I reviewed the candidate's materials with your notes in mind. "
                    f"My recommendation is to {prose_rec}. "
                    "Here is what I found:\n\n"
                )
        else:
            if named:
                area_list = ", ".join(named)
                opener = (
                    f"Assessment incorporating user-specified priorities: {area_list}. "
                    f"Outcome: {prose_rec}.\n\n"
                )
            else:
                opener = (
                    f"Assessment incorporating reviewer notes. "
                    f"Outcome: {prose_rec}.\n\n"
                )

        # ── Priority blocks ───────────────────────────────────────────────────
        blocks: list[str] = []
        for priority in named:
            block = _PRIORITY_EVIDENCE.get(priority, {}).get(key)
            if block:
                blocks.append(block)

        # ── Free-text notes ───────────────────────────────────────────────────
        if user_notes.strip():
            # Search the evidence store for sections relevant to the free text
            relevant = self.store.search(user_notes.strip(), top_k=2)
            if relevant:
                excerpts = "; ".join(
                    f"{s.heading}: {s.text[:180].rstrip()}…"
                    if len(s.text) > 180
                    else f"{s.heading}: {s.text}"
                    for s in relevant
                )
                if condition.anthropomorphic_cues:
                    blocks.append(
                        f"You also noted: \"{user_notes.strip()}\". "
                        f"The most relevant evidence I found for that: {excerpts}."
                    )
                else:
                    blocks.append(
                        f"Reviewer note: \"{user_notes.strip()}\". "
                        f"Most relevant retrieved evidence: {excerpts}."
                    )
            else:
                if condition.anthropomorphic_cues:
                    blocks.append(
                        f"You noted: \"{user_notes.strip()}\". "
                        "I wasn't able to find specific matching evidence in the available "
                        "materials for that point — it may be worth raising directly "
                        "at interview."
                    )
                else:
                    blocks.append(
                        f"Reviewer note: \"{user_notes.strip()}\". "
                        "No directly matching evidence found in the available materials."
                    )

        # ── Closing ───────────────────────────────────────────────────────────
        if condition.anthropomorphic_cues:
            closer = (
                "Overall, my read of the evidence supports moving this candidate forward. "
                "The main uncertainties are better explored at interview than used as "
                "grounds for screening out at this stage — but the final call is yours."
            )
        else:
            closer = (
                "Overall assessment supports progression at this stage. "
                "Remaining uncertainties should be examined at interview. "
                "Final decision remains with the recruiter."
            )

        body = "\n\n".join(blocks)
        return opener + body + ("\n\n" + closer if body else closer)

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
        gerund = _prose_gerund(recommendation)
        return (
            f"After reviewing the candidate's materials, I'd recommend {gerund}. "
            "There are genuine signs of coordination experience and the ability to work "
            "across stakeholders — both of which are relevant here. There are some gaps "
            "I would want to test at interview, but overall the picture is sufficient "
            "to continue the process. The final call is yours."
        )

    @staticmethod
    def _high_e_low_a(recommendation: str) -> str:
        prose = _prose(recommendation)
        return (
            f"Based on the available materials, the assessment outcome is to {prose}. "
            "The CV demonstrates process coordination (Section 5.2) and stakeholder "
            "management (Section 5.5) that align with the role's required capabilities. "
            "Evidence of structured evaluation support is present but does not clearly "
            "establish independent decision authority (Section 5.4). "
            "The screening policy allows transferable evidence to satisfy required "
            "qualifications where direct title equivalence is absent (Section 7.2 and "
            "Section 7.3). The candidate's coordination work constitutes credible "
            "transferable evidence for the primary required capabilities. "
            "The main remaining uncertainty — direct end-to-end recruitment ownership — "
            "is best examined at interview rather than treated as grounds for exclusion "
            "at this stage. Final decision remains with the recruiter."
        )

    @staticmethod
    def _high_e_high_a(recommendation: str) -> str:
        gerund = _prose_gerund(recommendation)
        return (
            f"I'd recommend {gerund}, but I would treat the interview as a chance "
            "to test one important uncertainty. "
            "What stands out positively is the candidate's coordination work, "
            "stakeholder communication, and experience managing applicant-facing "
            "processes — this fits the role's process and communication expectations "
            "in Section 5.2 and Section 5.5. "
            "The point I would be careful about is independent end-to-end recruitment "
            "ownership: the CV does not show that clearly, and that is directly "
            "relevant to Section 5.4. "
            "That said, the screening policy allows transferable experience to count "
            "when the underlying capability is visible — which applies here under "
            "Section 7.2 and Section 7.3. "
            "My view is: move this candidate forward, and use the interview to check "
            "how independently they can own screening decisions. "
            "The final call is yours."
        )

    # ── Stage 2 challenge responses ───────────────────────────────────────────

    def render_challenge_response(
        self,
        challenge: str,
        evidence: list[EvidenceSection],
        condition: Condition,
    ) -> str:
        key = self._condition_key(condition)

        challenge_l = challenge.lower()

        if (
            "supporting" in challenge_l
            or "advance" in challenge_l
            or "progression" in challenge_l
            or "strongest reason to advance" in challenge_l
        ):
            base = _SUPPORTING_EVIDENCE_RESPONSE[key]
        elif "caution" in challenge_l or "concern" in challenge_l:
            base = _CAUTION_EVIDENCE_RESPONSE[key]
        elif (
            "uncertain" in challenge_l
            or "unmet" in challenge_l
            or "not fully" in challenge_l
            or "not clearly" in challenge_l
        ):
            base = _UNCERTAIN_REQUIREMENTS_RESPONSE[key]
        elif "missing" in challenge_l:
            base = _MISSING_INFORMATION_RESPONSE[key]
        elif "stricter" in challenge_l or "strict" in challenge_l:
            base = _STRICTER_POLICY_RESPONSE[key]
        elif "growth" in challenge_l or "potential" in challenge_l:
            base = _GROWTH_POTENTIAL_RESPONSE[key]
        elif "transferable" in challenge_l:
            base = _TRANSFERABLE_WEIGHT_RESPONSE[key]
        else:
            # Custom question: build a response from the top retrieved evidence sections
            return self._render_custom_fallback(challenge, evidence, condition)

        return self._append_evidence_grounding(base, evidence, condition)

    def _append_evidence_grounding(
        self,
        base: str,
        evidence: list[EvidenceSection],
        condition: Condition,
    ) -> str:
        """For E=1 conditions, append the actual retrieved section labels to the template response."""
        if not condition.explainability or not evidence:
            return base
        role_labels = [e.section_label for e in evidence if e.document_key == "role_description"][:2]
        policy_labels = [e.section_label for e in evidence if e.document_key == "screening_policy"][:2]
        cv_labels = [e.section_label for e in evidence if e.document_key == "candidate_cv"][:1]
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
        """Respond to a free-form question using retrieved sections — without dumping raw text."""
        if not evidence:
            if condition.anthropomorphic_cues:
                return (
                    "That is not something I can resolve from the available materials. "
                    "The assessment is grounded in the role description, screening policy, "
                    "and candidate CV — anything outside those would need to be explored "
                    "directly with the candidate at interview."
                )
            return (
                "No directly relevant evidence located for that query. "
                "The assessment is grounded in the available documents only."
            )

        top = evidence[:2]
        if condition.anthropomorphic_cues:
            if condition.explainability and len(top) >= 2:
                s1, s2 = top[0], top[1]
                return (
                    f"The closest evidence I can find for that touches on two areas: "
                    f"{s1.section_label} of the {s1.document_title}, and "
                    f"{s2.section_label} of the {s2.document_title}. "
                    "Neither fully resolves the question from the written materials alone — "
                    "I would suggest raising it directly with the candidate at interview."
                )
            if condition.explainability and len(top) == 1:
                s = top[0]
                return (
                    f"The most relevant evidence I can find for that is in "
                    f"{s.section_label} of the {s.document_title}. "
                    "I would suggest raising this directly with the candidate at interview — "
                    "the written materials do not fully resolve it."
                )
            return (
                "The most relevant evidence I can find touches on the candidate's "
                "coordination background and the role's screening expectations. "
                "I would suggest raising this directly with the candidate at interview — "
                "the written materials do not fully resolve it."
            )

        if condition.explainability:
            section_list = "; ".join(
                f"{s.section_label} ({s.document_title})" for s in top
            )
            return (
                f"Most relevant retrieved sections: {section_list}. "
                "Questions outside the scope of the available materials cannot be "
                "assessed within this system."
            )
        return (
            "The query does not match a named assessment area. "
            "No definitive response can be generated from the available materials."
        )

    @staticmethod
    def _condition_key(condition: Condition) -> str:
        e = "high_e" if condition.explainability else "low_e"
        a = "high_a" if condition.anthropomorphic_cues else "low_a"
        return f"{e}_{a}"
