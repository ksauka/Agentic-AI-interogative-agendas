"""Experimental condition definitions shared by all Streamlit entry points."""

from dataclasses import dataclass


# ── Stage 1: assessment preference options (C=1) ───────────────────────────
FOCUS_AREAS = [
    "Independent ownership",
    "Communication and stakeholder management",
    "Transferable experience",
    "Screening and evaluation experience",
    "Operational coordination",
    "Growth potential",
    "Something else",
]

# ── Stage 2: additional review options — condition-dependent labels (C=1) ──
CHALLENGE_AREAS_HIGH_A = [
    "Show me the strongest evidence supporting interview progression",
    "Show me the strongest reason for caution",
    "Explain how transferable experience influenced the recommendation",
    "Explain which role requirements are not fully demonstrated",
    "Review the candidate using stricter criteria",
    "Review the candidate with greater emphasis on growth potential",
    "Ask a different question",
]

CHALLENGE_AREAS_LOW_A = [
    "Supporting evidence",
    "Caution evidence",
    "Transferable evidence interpretation",
    "Unmet requirements",
    "Stricter evaluation criteria",
    "Growth potential emphasis",
    "Other query",
]

# Legacy alias (kept for any external imports)
CHALLENGE_AREAS = CHALLENGE_AREAS_HIGH_A


def challenge_areas(condition: "Condition") -> list:
    """Return the Stage 2 option list appropriate for this condition's anthropomorphism level."""
    return CHALLENGE_AREAS_HIGH_A if condition.anthropomorphic_cues else CHALLENGE_AREAS_LOW_A

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
    """Return the Stage 1 assessment-preference invitation for C=1 conditions."""
    if not condition.mixed_initiative_control_cues:
        return ""
    if condition.anthropomorphic_cues:
        return (
            "Before I review the candidate, it would help me to understand what matters "
            "most to you for this role. Is there anything you would like me to pay "
            "particular attention to?"
        )
    return (
        "Select any areas that should receive additional attention during candidate assessment."
    )


def post_recommendation_prompt(condition: Condition) -> str:
    """Return the Stage 2 additional-review invitation for C=1 conditions."""
    if not condition.mixed_initiative_control_cues:
        return ""
    if condition.anthropomorphic_cues:
        return (
            "Before you make your final decision, would you like me to look more closely "
            "at any aspect of the candidate?"
        )
    return (
        "Additional assessment options are available before you make your final decision."
    )
