"""Experimental condition definitions shared by all Streamlit entry points."""

from dataclasses import dataclass


FOCUS_AREAS = [
    "Strategic leadership and decision-making capability",
    "Cross-functional collaboration and stakeholder management",
    "Technical and analytical proficiency",
    "Cultural fit and organisational values alignment",
    "Relevant domain expertise and track record",
]


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
            "Before I begin my analysis, I'd like to understand what matters most to you "
            "for this role. Please select the aspects you want me to prioritise, and feel "
            "free to add any specific concerns or criteria that should shape the assessment. "
            "Your input will be reflected in how I frame the recommendation — this is your "
            "agenda, not mine."
        )
    return (
        "Before the assessment is generated, identify the aspects most important for this "
        "role and optionally describe any specific priorities or concerns. These will be "
        "incorporated into the recommendation framing. The assessment agenda is set by you."
    )


def control_prompt(condition: Condition) -> str:
    if not condition.mixed_initiative_control_cues:
        return ""
    if condition.anthropomorphic_cues:
        return (
            "Now that I have your priorities, how would you like to proceed? "
            "You can inspect the retrieved evidence first to verify the basis of my "
            "assessment, or go straight to my recommendation. The final screening "
            "decision remains yours."
        )
    return (
        "With your stated priorities noted, select whether to inspect the strongest "
        "retrieved evidence first or view the recommendation directly. The final "
        "decision remains with the participant."
    )
