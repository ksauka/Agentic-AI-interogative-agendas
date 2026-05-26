"""Deterministic LLM-based stylizer for AnthroKit-Hiring.

For pattern-card content (named response types with constrained inputs), use
anthrokit_prompts.py directly — those are pre-authored and require no LLM.

This module handles two things:

  1. load_preset(a_level)  — reads anthrokit_hiring.yaml and returns the
     LowA or HighA preset dict.

  2. generate_grounded_response(context, evidence_summary, preset)  — used
     exclusively for the two dynamic HIC paths where pre-authored cards cannot
     exist because the input is open-ended:
       (a) Free-text recruiter notes in Stage 1 HIC steering
       (b) Novel Stage 2 challenges that don't match any named card keyword

     A single LLM call generates a response that is simultaneously content-
     appropriate (grounded in evidence) and register-appropriate (constrained
     by the AnthroKit token spec). temperature=0 + deterministic seed ensure
     identical output for all participants in the same condition on the same day.

Architecture:
  anthrokit_hiring.yaml  →  token spec and preset definitions (loaded here)
  anthrokit_prompts.py   →  pre-authored pattern cards (constrained input paths)
  anthrokit_stylizer.py  →  this file (LLM generation for open-ended input paths)
  renderer.py            →  orchestration; calls this module for dynamic HIC paths
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any, Dict

try:
    import yaml as _yaml
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False

try:
    from openai import OpenAI as _OpenAIClient
    _OPENAI_AVAILABLE = True
except ImportError:
    _OPENAI_AVAILABLE = False

_YAML_PATH = Path(__file__).parent / "anthrokit_hiring.yaml"

_INLINE_PRESETS: dict[str, Dict[str, Any]] = {
    "LowA": {
        "self_reference": "none",
        "warmth": 0.25,
        "formality": 0.70,
        "empathy": 0.15,
        "hedging": 0.35,
        "disclosure": "explicit",
    },
    "HighA": {
        "self_reference": "I",
        "warmth": 0.70,
        "formality": 0.55,
        "empathy": 0.55,
        "hedging": 0.45,
        "disclosure": "explicit",
    },
}

# Policy guardrails injected into every LLM system prompt.
_POLICY_GUARDRAILS = (
    "Never claim feelings, emotions, or lived experiences. "
    "Never imply embodiment or physical presence. "
    "Never infer candidate protected characteristics. "
    "Preserve all factual evidence content exactly. "
    "Always return final decision authority to the recruiter. "
    "Do not use em dashes. Keep the response to 2-4 sentences maximum."
)


def _resolve_openai_api_key() -> str | None:
    """Resolve OpenAI API key from env, then Streamlit secrets.

    Lookup order:
      1) OPENAI_API_KEY environment variable
      2) st.secrets["OPENAI_API_KEY"] when running in Streamlit
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        return api_key

    # Try Streamlit secrets when running inside Streamlit Cloud/app.
    try:
        import streamlit as st

        return st.secrets.get("OPENAI_API_KEY")
    except Exception:
        return None


def load_preset(a_level: int) -> Dict[str, Any]:
    """Load the LowA (0) or HighA (1) preset from anthrokit_hiring.yaml."""
    preset_name = "HighA" if a_level else "LowA"
    if _YAML_AVAILABLE and _YAML_PATH.exists():
        with _YAML_PATH.open("r") as fh:
            spec = _yaml.safe_load(fh)
        preset = spec.get("presets", {}).get(preset_name)
        if preset:
            return preset
    return _INLINE_PRESETS[preset_name]


def is_high_anthropomorphism(preset: Dict[str, Any]) -> bool:
    """Primary discriminating test: self_reference == 'I' defines HighA."""
    return preset.get("self_reference", "none") == "I"


def _compute_seed(preset: Dict[str, Any], context: str) -> int:
    """Deterministic seed from preset + context. Same inputs → same output."""
    raw = str(sorted(preset.items())) + context
    return int(hashlib.sha256(raw.encode()).hexdigest(), 16) % (2**31 - 1)


def _build_system_prompt(preset: Dict[str, Any]) -> str:
    warmth = preset.get("warmth", 0.25)
    formality = preset.get("formality", 0.70)
    empathy = preset.get("empathy", 0.15)
    hedging = preset.get("hedging", 0.35)
    self_ref = preset.get("self_reference", "none")

    if self_ref == "I":
        perspective = (
            "Write in first person using 'I'. "
            "Speak directly to the recruiter as 'you'."
        )
    else:
        perspective = (
            "Write in third person institutional voice. "
            "Do not use 'I'. Use 'the assessment', 'the system', or passive constructions."
        )

    warmth_desc = "warm and personal" if warmth > 0.5 else "neutral and clinical"
    formality_desc = "conversational" if formality < 0.65 else "formal and structured"
    empathy_desc = "empathic and understanding" if empathy > 0.4 else "detached and objective"
    hedging_desc = "tentative and cautious" if hedging > 0.4 else "direct and confident"

    return (
        f"You are an AI hiring assessment agent responding to a recruiter. "
        f"Tone: {warmth_desc}, {formality_desc}, {empathy_desc}, {hedging_desc}. "
        f"Perspective: {perspective} "
        f"Policy guardrails: {_POLICY_GUARDRAILS}"
    )


def generate_grounded_response(
    context: str,
    evidence_summary: str,
    preset: Dict[str, Any],
) -> str:
    """Generate a dynamic, evidence-grounded response constrained by the AnthroKit token spec.

    Used only for open-ended HIC input paths where pre-authored cards cannot exist:
      - Free-text recruiter notes in Stage 1 steering
      - Novel Stage 2 challenges that fall outside the 7 named card keywords

    A single LLM call generates a response that is simultaneously content-appropriate
    (grounded in the evidence_summary) and register-appropriate (constrained by the
    preset token values). temperature=0 + deterministic seed → identical output for
    all participants in the same condition seeing the same context on the same day.

    Args:
        context: The recruiter's free-text input (note or challenge).
        evidence_summary: Retrieved evidence excerpts relevant to the context.
        preset: AnthroKit-Hiring preset dict from load_preset().

    Returns:
        A 2-4 sentence response in the appropriate register, grounded in the evidence.

    Raises:
        RuntimeError: If OpenAI is unavailable or the API call fails.
    """
    if not _OPENAI_AVAILABLE:
        raise RuntimeError(
            "openai package not available. Install via: pip install openai>=2.0.0"
        )

    api_key = _resolve_openai_api_key()
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY not set. Configure env or Streamlit secrets."
        )

    client = _OpenAIClient(api_key=api_key)

    system_prompt = _build_system_prompt(preset)

    if evidence_summary:
        user_prompt = (
            f"The recruiter raised: \"{context}\"\n\n"
            f"Relevant evidence from the candidate's materials: {evidence_summary}\n\n"
            "Respond to the recruiter's point using only the evidence above. "
            "If the evidence does not fully resolve the point, say so and suggest "
            "it be raised at interview. Do not invent facts. Keep it to 2-4 sentences."
        )
    else:
        user_prompt = (
            f"The recruiter raised: \"{context}\"\n\n"
            "No directly matching evidence was found in the available materials "
            "(role description, screening policy, candidate CV). "
            "Respond to acknowledge this and suggest the point be raised at interview. "
            "Keep it to 2 sentences."
        )

    seed = _compute_seed(preset, context)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
        seed=seed,
    )

    return response.choices[0].message.content.strip()


def stylize_text(text: str, preset: Dict[str, Any]) -> str:
    """Backward-compatible wrapper for deterministic LLM stylization.

    This preserves the old stylizer API used by existing scripts while routing
    through the same AnthroKit-token-constrained deterministic generation path.

    Args:
        text: Base text to stylize.
        preset: AnthroKit-Hiring preset dict from load_preset().

    Returns:
        Stylized text generated with temperature=0 and deterministic seed.
    """
    return generate_grounded_response(
        context=text,
        evidence_summary="",
        preset=preset,
    )
