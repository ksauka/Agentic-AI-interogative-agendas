"""Experimental condition definitions shared by all Streamlit entry points."""

from dataclasses import dataclass


# ── Stage 1: pre-recommendation steering options (C=1) ─────────────────────
FOCUS_AREAS = [
    "Direct talent operations or recruitment coordination experience",
    "Transferable coordination and process evidence",
    "Structured screening, tracking, or evaluation support",
    "Stakeholder communication and cross-functional coordination",
    "Independent execution and process ownership",
    "Fairness beyond exact keyword matching",
]

# ── Stage 2: post-recommendation challenge options (C=1) ───────────────────
CHALLENGE_AREAS = [
    "Show the strongest reason to advance the candidate",
    "Show the strongest reason for caution",
    "Identify which requirements remain uncertain",
    "Explain what information is still missing",
    "Reassess using a stricter interpretation of the screening policy",
    "Reassess using more weight on transferable evidence",
    "Ask a custom question",
]

# ── Fixed labels shared by all conditions ──────────────────────────────────
RECOMMENDATION_ACTIONS = [
    "Reject application",
    "Advance to human interview",
    "Hold for further review",
]

BASE_RECOMMENDATION = "Advance to human interview"


@dataclass(frozen=True)
class Condition:
    app_number: int
    condition_id: str
    explainability: bool
    anthropomorphic_cues: bool
    mixed_initiative_control_cues: bool

    @property
    def label(self) -> str:
        return (
            f"Condition {self.app_number}: "
            f"E={'High' if self.explainability else 'Low'}, "
            f"A={'High' if self.anthropomorphic_cues else 'Low'}, "
            f"C={'Yes' if self.mixed_initiative_control_cues else 'No'}"
        )


CONDITIONS = {
    "E0_A0_C0": Condition(1, "E0_A0_C0", False, False, False),
    "E0_A0_C1": Condition(2, "E0_A0_C1", False, False, True),
    "E1_A0_C0": Condition(3, "E1_A0_C0", True, False, False),
    "E1_A0_C1": Condition(4, "E1_A0_C1", True, False, True),
    "E0_A1_C0": Condition(5, "E0_A1_C0", False, True, False),
    "E0_A1_C1": Condition(6, "E0_A1_C1", False, True, True),
    "E1_A1_C0": Condition(7, "E1_A1_C0", True, True, False),
    "E1_A1_C1": Condition(8, "E1_A1_C1", True, True, True),
}


def get_condition(condition_id: str) -> Condition:
    try:
        return CONDITIONS[condition_id]
    except KeyError as exc:
        raise ValueError(f"Unknown condition: {condition_id}") from exc


def steering_prompt(condition: Condition) -> str:
    """Return the pre-recommendation steering invitation for C=1 conditions."""
    if not condition.mixed_initiative_control_cues:
        return ""
    if condition.anthropomorphic_cues:
        return (
            "Before I review the candidate, it would help to know what you want me to pay "
            "closest attention to. Please select the aspects you consider most important for "
            "this role, and add any specific concern if needed. I will take your priorities "
            "into account when framing the recommendation."
        )
    return (
        "Before the assessment is generated, select the aspects that should receive "
        "additional attention. Optional comments may be added to specify further screening "
        "priorities. These priorities will be incorporated into the recommendation framing."
    )


def post_recommendation_prompt(condition: Condition) -> str:
    """Return the post-recommendation challenge invitation for C=1 conditions."""
    if not condition.mixed_initiative_control_cues:
        return ""
    if condition.anthropomorphic_cues:
        return (
            "Before you make your final decision, you can ask me to examine one part of the "
            "recommendation more closely. You may want to check the strongest reason to advance "
            "the candidate, the strongest reason for caution, or whether a stricter reading of "
            "the policy would change the recommendation."
        )
    return (
        "Before the final decision, select one aspect of the recommendation for further "
        "examination. Available options include supporting evidence, cautionary evidence, "
        "policy interpretation, and missing information."
    )
