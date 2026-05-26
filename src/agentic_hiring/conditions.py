"""Experimental condition definitions shared by all Streamlit entry points."""

from dataclasses import dataclass


# ── HIC Stage 1: assessment preference options (C=1) ──────────────────────────
# These are the checkbox labels shown to participants at HIC Stage 1.
# Internal research terms (MICC, interrogative agenda, steering) must not appear.
FOCUS_AREAS = [
    "Independent ownership",
    "Stakeholder communication",
    "Transferable experience",
    "Structured evaluation or screening experience",
    "Operational coordination",
    "Growth potential",
    "Other concern",
]

# ── HIC Stage 2: inspection options (C=1) ─────────────────────────────────────
# Participant-facing labels only. No internal research terms.
HIC_STAGE2_OPTIONS = [
    "Strongest evidence supporting progression",
    "Strongest reason for caution",
    "Transferable experience interpretation",
    "Unmet role requirements",
    "Stricter review",
    "Growth potential review",
    "Other question",
]

# Legacy aliases kept for backward compatibility
CHALLENGE_AREAS_HIGH_A = HIC_STAGE2_OPTIONS
CHALLENGE_AREAS_LOW_A = HIC_STAGE2_OPTIONS
CHALLENGE_AREAS = HIC_STAGE2_OPTIONS


def hic_stage2_options(condition: "Condition") -> list:
    """Return the HIC Stage 2 option list for this condition."""
    return HIC_STAGE2_OPTIONS


# Backward-compatibility alias
challenge_areas = hic_stage2_options

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
    hic: bool  # Human Intervention Checkpoints

    @property
    def mixed_initiative_control_cues(self) -> bool:
        """Backward-compatibility alias for hic."""
        return self.hic

    @property
    def label(self) -> str:
        return (
            f"Condition {self.app_number}: "
            f"E={'High' if self.explainability else 'Low'}, "
            f"A={'High' if self.anthropomorphic_cues else 'Low'}, "
            f"HIC={'Yes' if self.hic else 'No'}"
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


def hic_stage1_prompt(condition: "Condition") -> str:
    """Return the HIC Stage 1 invitation shown to participants before recommendation."""
    if not condition.hic:
        return ""
    if condition.anthropomorphic_cues:
        return (
            "Before I review the candidate, is there anything you would like me to pay "
            "particular attention to?"
        )
    return (
        "Before generating the assessment: select any areas that should receive "
        "closer attention during candidate review."
    )


# Backward-compatibility alias
steering_prompt = hic_stage1_prompt


def hic_stage2_prompt(condition: "Condition") -> str:
    """Return the HIC Stage 2 invitation shown after the recommendation."""
    if not condition.hic:
        return ""
    if condition.anthropomorphic_cues:
        return (
            "Before making your final decision, would you like me to look more closely "
            "at any aspect of the candidate?"
        )
    return (
        "Before you proceed to your final decision, you can request a closer look "
        "at any aspect of the assessment."
    )


# Backward-compatibility alias
post_recommendation_prompt = hic_stage2_prompt

