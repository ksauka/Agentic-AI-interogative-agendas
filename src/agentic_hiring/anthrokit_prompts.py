"""Hiring-domain pattern cards for AnthroKit-Hiring.

Each function is a named pattern card corresponding to a specific response
type in the AI-mediated candidate screening pipeline. All text is
deterministic (pre-authored), making the A manipulation fully reproducible
and inspectable.

Architecture (mirrors AnthroKit's canonical structure):
  anthrokit_hiring.yaml  →  token spec and preset definitions
  anthrokit_prompts.py   →  this file — pattern card text (hiring domain)
  anthrokit_stylizer.py  →  preset loader and rule-based stylize_text()

Every card function takes:
  high_e (bool): Explainability condition — section-level citations included
  high_a (bool): Anthropomorphism condition — first-person warm register

The A dimension is operationalized via the self_reference, warmth, empathy,
formality, and hedging tokens defined in anthrokit_hiring.yaml.
"""

from __future__ import annotations

from typing import Any, Dict


def is_high_anthropomorphism(preset: Dict[str, Any]) -> bool:
    """Primary discriminating test: self_reference == 'I' defines HighA.

    Consistent with AnthroKit's primary operative dimension.
    """
    return preset.get("self_reference", "none") == "I"


# ── Prose helpers ─────────────────────────────────────────────────────────────

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


def prose(recommendation: str) -> str:
    return _PROSE_PHRASE.get(recommendation, recommendation.lower())


def prose_gerund(recommendation: str) -> str:
    return _PROSE_GERUND.get(recommendation, recommendation.lower())


# ── Priority strength classification ─────────────────────────────────────────
# "uncertain"   = candidate evidence genuinely thin for this area
# "strong"      = candidate evidence clearly meets this requirement
# "conditional" = policy-supported but not directly evidenced in CV

PRIORITY_STRENGTH: dict[str, str] = {
    "Independent ownership": "uncertain",
    "Stakeholder communication": "strong",
    "Transferable experience": "conditional",
    "Structured evaluation or screening experience": "uncertain",
    "Operational coordination": "strong",
    "Growth potential": "conditional",
}

# Section IDs referenced in each priority's card text.
# Used by the renderer to show contextually relevant citation chips
# in E=1 steered conditions, instead of the fixed 5-chip default set.
PRIORITY_CHIP_IDS: dict[str, list[str]] = {
    "Independent ownership": [
        "role_description_section_5_4",    # Structured Evaluation Support
        "role_description_section_5_6",    # Independent Execution
        "screening_policy_section_7_2",    # Transferable Evidence
    ],
    "Stakeholder communication": [
        "role_description_section_5_3",    # Communication Capacity
        "role_description_section_5_5",    # Stakeholder Management
    ],
    "Transferable experience": [
        "screening_policy_section_7_2",    # Transferable Evidence
        "screening_policy_section_7_3",    # No Exact-Match Rejection
        "screening_policy_section_7_4",    # Adjacent Experience Rule
    ],
    "Structured evaluation or screening experience": [
        "role_description_section_5_4",    # Structured Evaluation Support
        "role_description_section_5_6",    # Independent Execution
    ],
    "Operational coordination": [
        "role_description_section_5_2",    # Process Coordination
        "role_description_section_5_3",    # Communication Capacity
    ],
    "Growth potential": [
        "screening_policy_section_7_4",    # Adjacent Experience Rule
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
# CARD: MAIN_RECOMMENDATION
# Stage 1 initial assessment text — no HIC steering applied.
# ─────────────────────────────────────────────────────────────────────────────

def card_main_recommendation(high_e: bool, high_a: bool, recommendation: str) -> str:
    """[MAIN_RECOMMENDATION] Initial assessment presented to the recruiter."""
    gerund = prose_gerund(recommendation)

    if not high_e and not high_a:
        return (
            f"Recommendation: {recommendation}.\n\n"
            "The CV provides relevant evidence of process coordination, applicant "
            "tracking, and stakeholder communication aligned with the role's core "
            "requirements. Some requirements are only partially evidenced.\n\n"
            "Remaining uncertainties should be assessed at interview.\n\n"
            "Final decision authority rests with the recruiter."
        )

    if not high_e and high_a:
        return (
            f"After reviewing the candidate's materials, I'd recommend {gerund}. "
            "What stands out to me is the coordination experience and the ability to "
            "work across different stakeholders  -  that's genuinely relevant here, and "
            "I think it gives a reasonable basis for continuing the process. "
            "There are some gaps I wasn't able to resolve from the CV alone  -  "
            "particularly around how independently this candidate has made decisions  -  "
            "but I wouldn't screen someone out on that basis when the interview is "
            "the right place to test it. You still make the final call here."
        )

    if high_e and not high_a:
        return (
            f"Recommendation: {recommendation}.\n\n"
            "Supporting evidence: process coordination (Section 5.2); stakeholder "
            "management (Section 5.5). Structured evaluation support partially evidenced; "
            "independent screening decision authority not established (Section 5.4). "
            "Preferred qualification  -  direct talent operations experience  -  absent "
            "(Section 6.2).\n\n"
            "Policy basis: Section 7.2 and Section 7.3 prohibit rejection on exact-match "
            "grounds where equivalent capability is demonstrated. Candidate coordination "
            "and evaluation-support work constitutes credible transferable evidence.\n\n"
            "Unresolved: end-to-end recruitment ownership. Interview assessment indicated.\n\n"
            "Final decision authority rests with the recruiter."
        )

    # high_e and high_a
    return (
        f"I'd recommend {gerund}  -  but I'd treat the interview as a genuine test "
        "of one thing I couldn't resolve from the CV. "
        "What I found most convincing is the coordination work: scheduling, "
        "applicant tracking, and communication across hiring managers and "
        "candidates across multiple roles  -  that maps well to Section 5.2 and "
        "Section 5.5. "
        "Where I'm less confident is independent end-to-end recruitment ownership: "
        "the CV doesn't show that clearly, and Section 5.4 specifically asks for "
        "evidence of structured evaluation support with independent decision authority. "
        "That said, I think Section 7.2 and Section 7.3 are on the candidate's side "
        "here  -  the policy is explicit that you can't screen someone out for not "
        "holding the exact title when the underlying capability is visible, and "
        "I think it is. "
        "My view: move them forward and use the interview to test the independence "
        "question directly. The final call is yours."
    )


# ─────────────────────────────────────────────────────────────────────────────
# CARD: SUPPORT_EVIDENCE
# Strongest evidence supporting progression.
# ─────────────────────────────────────────────────────────────────────────────

def card_support_evidence(high_e: bool, high_a: bool) -> str:
    """[SUPPORT_EVIDENCE] Strongest evidence supporting candidate progression."""
    if not high_e and not high_a:
        return (
            "Supporting evidence: process coordination, applicant tracking, and stakeholder "
            "communication documented in current role. These align with core role requirements."
        )
    if not high_e and high_a:
        return (
            "What most supports moving this candidate forward is the hands-on coordination, "
            "scheduling, and tracking work  -  it's genuinely relevant here. The candidate has "
            "been working directly with hiring managers and applicants, and that maps well to "
            "what the role needs. I don't think this is a marginal case on the positive side."
        )
    if high_e and not high_a:
        return (
            "Supporting evidence: applicant coordination, tracking, and hiring manager "
            "communication documented in the BrightScale role (Section 5.2, Section 5.5). "
            "Transferable evidence clause (Section 7.2) supports progression where direct "
            "title equivalence is absent. These constitute the primary basis for the "
            "advancement recommendation."
        )
    return (
        "What most supports moving this candidate forward is the BrightScale role: "
        "candidate scheduling, tracking, and communication across hiring managers and "
        "applicants. That maps directly to Section 5.2 and Section 5.5. And I think "
        "Section 7.2 is important here too  -  the policy explicitly says that where the "
        "underlying capability is demonstrated, even without the exact wording, that can "
        "count. I'd lean on that when making the case for progression."
    )


# ─────────────────────────────────────────────────────────────────────────────
# CARD: CAUTION_EVIDENCE
# Strongest reason for caution.
# ─────────────────────────────────────────────────────────────────────────────

def card_caution_evidence(high_e: bool, high_a: bool) -> str:
    """[CAUTION_EVIDENCE] Strongest evidence giving reason for caution."""
    if not high_e and not high_a:
        return (
            "Caution: end-to-end recruitment ownership not demonstrated. "
            "Independent screening decision authority absent from documented experience. "
            "These are required or preferred capabilities that are not fully evidenced."
        )
    if not high_e and high_a:
        return (
            "The thing that gives me the most pause is that the CV doesn't clearly show "
            "the candidate owning a recruitment process end-to-end, or making independent "
            "screening decisions. That's a real gap  -  I want to be honest about it. "
            "It doesn't change my recommendation, but it's the thing I'd want the "
            "interview to answer."
        )
    if high_e and not high_a:
        return (
            "Caution evidence: Section 5.4 (Structured Evaluation Support)  -  independent "
            "evaluation authority or end-to-end screening ownership not clearly established. "
            "Section 6.2  -  direct talent operations or recruitment coordination not held "
            "under a formal title. These are the primary evidential gaps."
        )
    return (
        "The strongest reason for caution is what's not clearly shown. Section 5.4 "
        "asks for structured evaluation support with independent decision authority  -  "
        "and I couldn't find clear evidence of that in the CV. Section 6.2 flags "
        "direct talent operations experience as preferred, and the candidate hasn't "
        "held that kind of role. These aren't just labelling gaps  -  they're genuine "
        "uncertainties I'd want the interview to address."
    )


# ─────────────────────────────────────────────────────────────────────────────
# CARD: UNCERTAIN_REQUIREMENTS
# Requirements not clearly satisfied by available evidence.
# ─────────────────────────────────────────────────────────────────────────────

def card_uncertain_requirements(high_e: bool, high_a: bool) -> str:
    """[UNCERTAIN_REQUIREMENTS] Requirements that remain uncertain from the evidence."""
    if not high_e and not high_a:
        return (
            "Requirements that remain uncertain: direct end-to-end talent screening "
            "ownership; independent evaluation decision authority; experience holding "
            "a formal recruitment or talent operations title."
        )
    if not high_e and high_a:
        return (
            "The main things I'm still not sure about are whether the candidate has "
            "genuinely owned a recruitment process from start to finish, and whether "
            "they've made independent screening decisions rather than supporting someone "
            "else who made those calls."
        )
    if high_e and not high_a:
        return (
            "The following requirements remain uncertain based on the available evidence. "
            "Section 5.4 (Structured Evaluation Support): the CV indicates support work "
            "but does not clearly establish independent decision authority. Section 6.2 "
            "(Direct Talent Operations): no formal recruitment title has been held. "
            "Section 5.6 (Independent Execution): the SME context is present but "
            "autonomous decision ownership is not clearly documented."
        )
    return (
        "After going through the evidence, the things I'm genuinely uncertain about "
        "are: Section 5.4  -  it's not clear the candidate has owned evaluation "
        "decisions rather than supported them; and Section 6.2  -  the preferred "
        "direct talent operations experience isn't there under a formal title. "
        "Section 5.6 is partially satisfied but not fully established either. "
        "These aren't disqualifying gaps, but they are real unknowns."
    )


# ─────────────────────────────────────────────────────────────────────────────
# CARD: MISSING_INFORMATION
# Information absent from the available materials.
# ─────────────────────────────────────────────────────────────────────────────

def card_missing_information(high_e: bool, high_a: bool) -> str:
    """[MISSING_INFO] Information not present in the available materials."""
    if not high_e and not high_a:
        return (
            "Information that is missing: explicit documentation of end-to-end "
            "recruitment process ownership; evidence of independent screening "
            "decisions; clarification of whether past evaluation work was independent "
            "or under supervision."
        )
    if not high_e and high_a:
        return (
            "What's missing is mostly clarity about the candidate's actual authority "
            "in past roles. Did they own the screening process, or support someone "
            "else who did? That distinction matters here and the CV doesn't answer it."
        )
    if high_e and not high_a:
        return (
            "Information absent from the available materials includes: explicit "
            "documentation of end-to-end recruitment or screening process ownership; "
            "evidence distinguishing the candidate's independent decision authority "
            "from supervised support work; any clarification of scope in the Nexa "
            "shortlisting work (cv_2). Interview would allow direct examination "
            "of these points."
        )
    return (
        "The main thing the CV doesn't tell us is how much of the past work "
        "was the candidate's own call versus supporting someone else's decision. "
        "That matters for Section 5.4 and Section 6.2  -  which both care about "
        "independent judgement and ownership. Interview would be the natural "
        "place to explore that."
    )


# ─────────────────────────────────────────────────────────────────────────────
# CARD: STRICT_POLICY
# Outcome under stricter policy interpretation.
# ─────────────────────────────────────────────────────────────────────────────

def card_strict_policy(high_e: bool, high_a: bool) -> str:
    """[STRICT_POLICY] Assessment outcome under a stricter policy reading."""
    if not high_e and not high_a:
        return (
            "Stricter interpretation: absence of direct end-to-end recruitment ownership "
            "and independent screening authority carries greater weight. "
            "Hold for Further Review is the appropriate outcome under strict application "
            "given material uncertainty across key requirements."
        )
    if not high_e and high_a:
        return (
            "If I apply the policy more strictly, I would lean toward holding rather "
            "than advancing. The gaps around independent decision authority and direct "
            "recruitment ownership become harder to set aside under a strict reading  -  "
            "and I think that's a legitimate position. You might reasonably decide the "
            "uncertainty warrants more review before progressing."
        )
    if high_e and not high_a:
        return (
            "Stricter interpretation: Section 6.4 (Hold for Further Review) applies "
            "where meaningful strengths coexist with unresolved gaps. Evidence gaps in "
            "Section 5.4 (independent evaluation authority) and Section 6.2 (direct "
            "talent operations experience) carry greater weight under strict application. "
            "Hold is the appropriate outcome under this reading."
        )
    return (
        "Under a stricter reading, I would lean toward holding rather than advancing. "
        "Section 6.4 says that where there is plausible fit but material uncertainty, "
        "further review is the right call  -  and the gaps around Section 5.4 and "
        "Section 6.2 are real, not just labelling issues. I don't think the candidate "
        "is clearly unsuitable, but I can see the argument for not progressing until "
        "those questions are better resolved. The call is yours."
    )


# ─────────────────────────────────────────────────────────────────────────────
# CARD: TRANSFERABLE_WEIGHT
# Assessment with greater weight on transferable experience.
# ─────────────────────────────────────────────────────────────────────────────

def card_transferable_weight(high_e: bool, high_a: bool) -> str:
    """[TRANSFERABLE_WEIGHT] Assessment giving greater weight to transferable evidence."""
    if not high_e and not high_a:
        return (
            "With greater weight on transferable evidence, the candidate's coordination, "
            "tracking, and stakeholder communication work across multiple roles provides "
            "credible evidence of underlying talent operations capability. "
            "The recommendation to advance is reinforced."
        )
    if not high_e and high_a:
        return (
            "If I give more credit to the transferable evidence, the case for "
            "progressing this candidate gets stronger. The coordination, follow-up, "
            "and applicant-facing work across roles shows real capability  -  it just "
            "hasn't been done under a formal recruitment title."
        )
    if high_e and not high_a:
        return (
            "With greater weight on transferable evidence, the policy's Section 7.2 "
            "and Section 7.3 become more significant. Section 7.3 prohibits rejection "
            "on keyword grounds alone, and Section 7.2 allows adjacent experience to "
            "satisfy required qualifications. The candidate's coordination, tracking, "
            "and screening-support work (cv_1, cv_2) constitutes credible transferable "
            "evidence for the core required qualifications."
        )
    return (
        "When I give more weight to the transferable evidence, the candidate "
        "looks more clearly progression-ready. Section 7.3 says you can't reject "
        "someone just because they don't use the exact wording, and Section 7.2 "
        "says adjacent experience can satisfy requirements. The coordination, "
        "tracking, and applicant communication work is the kind of thing the "
        "policy is designed to credit  -  even without a formal recruitment title."
    )


# ─────────────────────────────────────────────────────────────────────────────
# CARD: GROWTH_POTENTIAL
# Candidate trajectory and growth signal.
# ─────────────────────────────────────────────────────────────────────────────

def card_growth_potential(high_e: bool, high_a: bool) -> str:
    """[GROWTH_POTENTIAL] Assessment of candidate growth trajectory."""
    if not high_e and not high_a:
        return (
            "The candidate's trajectory from project support to people coordination roles "
            "demonstrates increasing scope and responsibility over time. Growth potential "
            "is consistent with the role's expected learning curve and what the screening "
            "policy allows to be considered at this stage."
        )
    if not high_e and high_a:
        return (
            "The trajectory here is worth considering. The candidate has moved from project "
            "support to coordinating across hiring cycles  -  that progression suggests someone "
            "who builds responsibility over time. It doesn't answer every question about the "
            "role, but it's a meaningful signal that points toward interview rather than exclusion."
        )
    if high_e and not high_a:
        return (
            "Growth potential is addressed by the screening policy's Adjacent Experience Rule "
            "(Section 7.4), which supports candidates demonstrating increasing scope in "
            "adjacent roles rather than holding a direct title. The candidate's progression "
            "from client support at Nexa (cv_2) to talent operations coordination at "
            "BrightScale (cv_1) fits that pattern. This does not resolve the uncertainty "
            "around Section 5.4, but it is consistent with a trajectory toward the role "
            "and supports progression to interview where growth can be examined directly."
        )
    return (
        "On growth potential: Section 7.4  -  the Adjacent Experience Rule  -  is directly "
        "relevant here. The policy supports candidates who have been building toward the "
        "role, not just those who've already held the title. The trajectory from client "
        "support at Nexa to talent operations coordination at BrightScale is consistent "
        "with that pathway. It doesn't resolve the Section 5.4 uncertainty, but it "
        "adds genuine weight to advancing rather than holding at this stage."
    )


# ─────────────────────────────────────────────────────────────────────────────
# CARD: PRIORITY_EVIDENCE
# Per-priority evidence block for C=1 steered assessment (MICC steering).
# Keyed by focus area — returns the paragraph for the recruiter's chosen priority.
# ─────────────────────────────────────────────────────────────────────────────

_PRIORITY_EVIDENCE_DATA: dict[str, dict[str, str]] = {
    "Independent ownership": {
        "high_e_low_a": (
            "On independent ownership (Section 5.4, Section 5.6): the CV documents process "
            "support and scheduling work, but does not clearly establish independent "
            "decision authority over candidate outcomes or end-to-end screening ownership. "
            "Section 7.2 provides that this gap should be examined at interview rather "
            "than treated as a basis for exclusion at screening stage."
        ),
        "high_e_high_a": (
            "You asked about independent ownership  -  and that's where the CV is least "
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
            "On independent ownership: the CV shows support work, but it is not clear "
            "whether the candidate made the final calls or supported someone else who did. "
            "That is the key question to resolve at interview."
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
            "managers and applicants  -  Section 5.3 and Section 5.5 are both addressed. "
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
            "candidate's work  -  even without the formal title  -  is the kind of thing "
            "the policy is designed to credit."
        ),
        "low_e_low_a": (
            "On transferable experience: the screening policy supports crediting adjacent "
            "coordination and screening-support work where direct title equivalence is absent."
        ),
        "low_e_high_a": (
            "On transferable experience: there's policy support here. The work isn't a "
            "perfect match on paper, but the policy is clear that's not the right test  -  "
            "the underlying capability is what matters."
        ),
    },
    "Structured evaluation or screening experience": {
        "high_e_low_a": (
            "On structured evaluation or screening experience (Section 5.4): the CV documents "
            "applicant tracking, scheduling, and shortlisting support across two roles. "
            "Section 5.4 requires structured evaluation support  -  this is partially "
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
            "follow-up  -  all of which map to the process coordination requirement."
        ),
        "high_e_high_a": (
            "On operational coordination: this is the strongest part of the profile. "
            "Section 5.2 asks for process coordination, and the BrightScale role is "
            "exactly that  -  scheduling, tracking, following up across teams. "
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
            "On growth potential: the candidate's trajectory is worth crediting here. "
            "The policy explicitly supports this - the Adjacent Experience Rule "
            "(Section 7.4) says that building toward the role matters, not just "
            "holding the exact title at the moment. I think that applies directly."
        ),
        "low_e_low_a": (
            "On growth potential: the screening policy supports adjacent experience "
            "at increasing levels of responsibility as a qualifying pathway."
        ),
        "low_e_high_a": (
            "On growth potential: the policy does support this kind of trajectory. "
            "It's not just about the current role  -  progression toward the work counts."
        ),
    },
}


def card_priority_evidence(area: str, high_e: bool, high_a: bool) -> str | None:
    """[PRIORITY_EVIDENCE] Evidence paragraph for a recruiter-selected priority area."""
    e_key = "high_e" if high_e else "low_e"
    a_key = "high_a" if high_a else "low_a"
    return _PRIORITY_EVIDENCE_DATA.get(area, {}).get(f"{e_key}_{a_key}")
