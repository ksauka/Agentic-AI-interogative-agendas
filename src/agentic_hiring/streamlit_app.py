"""Shared Streamlit interface for all eight experimental conditions.

Qualtrics/Prolific integration mirrors DS_Project simple_banking_assistant.py.
GitHub session logging mirrors DS_Project data_logger.py / github_saver.py.
Screen width follows anthrokit 860 px reading column.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import parse_qsl, unquote, urlencode, urlparse, urlunparse

import streamlit as st

from .conditions import (
    Condition,
    FOCUS_AREAS,
    HIC_STAGE2_OPTIONS,
    hic_stage1_prompt,
    hic_stage2_prompt,
    RECOMMENDATION_ACTIONS,
    BASE_RECOMMENDATION,
    get_condition,
)
from .decision_agent import AgenticHiringDecisionAgent, create_decision_agent
from .logger import EventLogger, restored_logger
from .schemas import AgentState, EvidenceSection
from .theme import apply_anthrokit_theme, show_study_banner, show_study_progress

# ─── Fixed study case ─────────────────────────────────────────────────────────

CANDIDATE_NAME = "Yuna Suvh"

CV_MARKDOWN = """\
# Yuna Suvh
**People and Operations Coordinator**  
Amsterdam, Netherlands · y.suvh@example.com

---

## Professional Summary

Operations and coordination professional with experience supporting cross-functional
teams in fast-moving business environments. Works across talent coordination, internal
process follow-up, stakeholder communication, and structured documentation.
Comfortable handling multiple priorities, improving workflow clarity, and supporting
hiring-related activities, though not always under formal recruitment role titles.

---

## Work Experience

### People and Operations Coordinator — BrightScale Commerce
*March 2022 – present · Amsterdam, Netherlands*

- Coordinated candidate scheduling, hiring follow-ups, and communication between
  hiring managers and applicants across multiple open roles
- Maintained internal tracking sheets for candidate progress and interview stages;
  flagged gaps and delays to line managers
- Supported preparation of structured interview packs and evaluation notes; did not
  hold independent decision authority over outcomes
- Improved internal follow-up process for open roles, reducing missed communication
  steps
- Worked with leadership and team leads on onboarding preparation and role handover

### Project and Client Support Associate — Nexa Solutions
*July 2019 – February 2022 · Rotterdam, Netherlands*

- Managed communication across client, operations, and delivery teams in a growing SME
- Tracked project stages, deadlines, and action items using structured internal
  workflows
- Prepared meeting summaries, follow-up records, and stakeholder updates
- Assisted with shortlisting external contractors for project support roles; was not
  the final decision-maker on these engagements

---

## Education

**BSc in Business Administration** — Bazeley Bridge Metropolitan University, 2019

---

## Skills

Stakeholder coordination · Workflow documentation · Process tracking ·
Cross-functional communication · Scheduling and follow-up · Operational support ·
Onboarding preparation · Spreadsheet tracking · Basic ATS exposure

---
"""

ROLE_SUMMARY = """\
**Role:** Strategic Talent Operations Partner — *Northstar Health Analytics*

| Requirement | Type |
|---|---|
| Process coordination: structured multi-stakeholder processes, tracking records | **Required** |
| Screening judgement: applying evaluation criteria to screening decisions | **Required** |
| Communication with hiring managers and candidates | **Required** |
| Direct end-to-end recruitment screening experience (fast-growing org) | Preferred |
"""

POLICY_SUMMARY = """\
**Recruiter Screening Policy — Key Rules**

1. **Evidence rule:** Ground recommendations in company context, the role description, the screening policy, and candidate CV evidence.
2. **Equivalent experience rule:** Comparable coordination or evaluation work can substitute for direct experience.
3. **Uncertainty rule:** Where evidence is mixed, consider whether uncertainty is best resolved through interview, further review, or non-progression.
"""

HOLD_UNRESOLVED_OPTIONS = [
    "Screening judgement capability not yet evidenced",
    "Direct end-to-end recruitment experience unclear",
    "Scope of independent decision-making authority unclear",
    "Candidate's role in past evaluation processes ambiguous",
    "Other",
]

AGENCY_ITEMS = [
    "I felt my judgement was the primary basis for the final outcome",
    "I found it easy to understand how the AI reached its recommendation",
    "I felt comfortable reaching a decision that differed from the AI's recommendation",
    "I felt I had meaningful control over the final decision",
    "The AI's output reflected what I considered important about this candidate",
    "I felt like an active participant rather than a passive reviewer",
    "The AI assistant made the screening task easier to complete",
    "The screening process felt transparent to me",
]

RELIANCE_ITEMS = [
    "I relied heavily on the AI's recommendation in reaching my decision",
    "I would have reached the same decision without the AI",
    "The AI recommendation changed my initial assessment of the candidate",
]

# ─── Qualtrics / Prolific helpers ─────────────────────────────────────────────

def _as_str(val) -> str:
    return str(val) if val else ""


def _is_safe_return(ru: str) -> bool:
    if not ru:
        return False
    try:
        decoded = unquote(ru)
        if not decoded.startswith(("http://", "https://")):
            decoded = "https://" + decoded
        p = urlparse(decoded)
        return (p.scheme in ("http", "https")) and ("qualtrics.com" in p.netloc)
    except Exception:
        return False


def _build_final_return(done: bool = True) -> Optional[str]:
    rr = st.session_state.get("return_raw", "")
    if not rr or not _is_safe_return(rr):
        return None
    decoded = unquote(rr)
    if not decoded.startswith(("http://", "https://")):
        decoded = "https://" + decoded
    p = urlparse(decoded)
    q = dict(parse_qsl(p.query, keep_blank_values=True))
    pid = st.session_state.get("prolific_pid", "")
    sid = st.session_state.get("session_id", "")
    cond = st.session_state.get("study_cond", "")
    if "PROLIFIC_PID" not in q and pid:
        q["PROLIFIC_PID"] = pid
    if "session_id" not in q and sid:
        q["session_id"] = sid
    if "cond" not in q and cond:
        q["cond"] = cond
    if "done" not in q:
        q["done"] = "1" if done else "0"
    return urlunparse(p._replace(query=urlencode(q, doseq=True)))


def back_to_survey(done_flag: bool = True) -> None:
    if st.session_state.get("_returned", False):
        return
    final = _build_final_return(done=done_flag)
    if not final:
        st.warning("No return URL detected. Please close this tab and return to your survey.")
        return
    st.session_state._returned = True
    st.markdown(
        f'<meta http-equiv="refresh" content="0;url={final}">',
        unsafe_allow_html=True,
    )
    st.stop()


def _read_qualtrics_params() -> None:
    """Read URL params once per session and persist to session_state."""
    try:
        qs = dict(st.query_params)
    except Exception:
        qs = {}
    pid_in = _as_str(qs.get("pid", ""))
    cond_in = _as_str(qs.get("cond", ""))
    ret_in = _as_str(qs.get("return", ""))
    prolific_pid = _as_str(qs.get("PROLIFIC_PID", ""))

    if "pid" not in st.session_state and pid_in:
        st.session_state.pid = pid_in
    if "study_cond" not in st.session_state and cond_in:
        st.session_state.study_cond = cond_in
    if "return_raw" not in st.session_state and ret_in:
        st.session_state.return_raw = ret_in
    if "prolific_pid" not in st.session_state:
        if prolific_pid:
            st.session_state.prolific_pid = prolific_pid
        elif pid_in:
            st.session_state.prolific_pid = pid_in
    if "_returned" not in st.session_state:
        st.session_state._returned = False
    if st.session_state.get("_returned"):
        final = _build_final_return(done=True)
        if final:
            st.markdown(
                f'<meta http-equiv="refresh" content="0;url={final}">',
                unsafe_allow_html=True,
            )
            st.stop()


def _prolific_gate() -> None:
    """Block the app until a Prolific/participant ID is confirmed."""
    if st.session_state.get("prolific_pid"):
        return
    st.info("Please enter your Prolific ID to begin the study task.")
    prolific_input = st.text_input(
        "Prolific ID",
        placeholder="e.g., 5f8e3c2a1b9d4e6f7a8b9c0d",
        help="This links your interactions to your survey responses.",
        key="prolific_id_input",
    )
    if st.button("Continue", type="primary", key="prolific_continue"):
        if prolific_input.strip():
            st.session_state.prolific_pid = prolific_input.strip()
            st.session_state.pid = prolific_input.strip()
            st.rerun()
        else:
            st.error("Please enter your Prolific ID to continue.")
    st.stop()


# ─── GitHub session saving ────────────────────────────────────────────────────

def _get_github_credentials() -> tuple[Optional[str], Optional[str]]:
    token, repo = None, None
    try:
        token = st.secrets.get("GITHUB_DATA_TOKEN") or st.secrets.get("GITHUB_TOKEN")
        repo = st.secrets.get("GITHUB_DATA_REPO") or st.secrets.get("GITHUB_REPO")
    except Exception:
        pass
    if not token:
        token = os.getenv("GITHUB_DATA_TOKEN") or os.getenv("GITHUB_TOKEN")
    if not repo:
        repo = os.getenv("GITHUB_DATA_REPO") or os.getenv("GITHUB_REPO")
    return token, repo


def _save_session_to_github(state: dict, condition: Condition, logger: EventLogger) -> bool:
    """Attach completion metadata to logger and push session to GitHub."""
    token, repo = _get_github_credentials()
    logger.session_meta = {
        "prolific_pid": state.get("prolific_pid", ""),
        "condition_id": condition.condition_id,
        "explainability": condition.explainability,
        "anthropomorphic_cues": condition.anthropomorphic_cues,
        "hic": condition.hic,
        "session_start": state.get("session_start", ""),
        "candidate_name": CANDIDATE_NAME,
        "hic_stage1": {
            "user_focus_areas": state.get("user_focus_areas", []),
            "user_focus_text": state.get("user_focus_text", ""),
            "user_focus": state.get("user_focus", ""),
        },
        "hic_stage2": {
            "hic2_option": state.get("hic2_option", ""),
            "stage2_done": state.get("stage2_done", False),
        },
        "decision": {
            "final_decision": state.get("decision", ""),
            "hold_reasons": state.get("hold_reasons", []),
            "ai_recommendation": state.get("ai_recommendation", ""),
            "recommendation_followed": (
                state.get("decision", "") == state.get("ai_recommendation", "")
            ),
        },
        "judgement_settledness": state.get("judgement_settledness"),
        "provenance_clicks": state.get("provenance_clicks", 0),
        "role_full_viewed": state.get("role_full_viewed", False),
        "policy_full_viewed": state.get("policy_full_viewed", False),
        "screen_dwell_times": state.get("screen_enter_times", {}),
        "questionnaire": state.get("questionnaire_responses", {}),
    }
    return logger.push_to_github(repo=repo, github_token=token)


# ─── App state ────────────────────────────────────────────────────────────────

def _state_key(condition: Condition) -> str:
    return f"hiring_study_{condition.condition_id}"


def _initial_state() -> dict:
    return {
        "stage": 0,
        "participant_id": "",
        "prolific_pid": "",
        "session_id": "",
        "session_start": "",
        "turn_id": 0,
        # HIC Stage 1: pre-recommendation checkpoint (C=1)
        "hic1_completed": False,
        "user_focus_areas": [],
        "user_focus_text": "",
        "user_focus": "",
        # HIC Stage 2: post-recommendation checkpoint (C=1)
        "hic2_option": "",
        "hic2_count": 0,  # incremented each submission to reset selectbox widget
        "stage2_done": False,
        "reco_generated": False,
        # Judgement settledness (shown after recommendation and any Stage 2 challenge)
        "judgement_settledness": None,
        "judgement_settledness_logged": False,
        # Logging sentinels
        "recommendation_logged": False,
        "evidence_inspection_logged": False,
        "session_saved": False,
        # Assessment / agent state cache
        "assessment": None,
        "agent_state": None,
        "ai_recommendation": "",
        "_challenge_text": "",
        # Citation navigation
        "highlight_section": None,
        # Final decision
        "decision": "",
        "hold_reasons": [],
        # Document inspection
        "role_full_viewed": False,
        "policy_full_viewed": False,
        "provenance_clicks": 0,
        # Timing
        "screen_enter_times": {},
        # Document navigation (full-doc sub-views)
        "doc_view": None,
        "doc_view_from": None,
        # Questionnaire
        "questionnaire_responses": {},
    }




def _log(logger: EventLogger, state: dict, event_type: str, **fields) -> None:
    logger.log(event_type, **fields)
    state["turn_id"] = logger.turn_id


def _record_screen_entry(state: dict, screen: int) -> None:
    key = str(screen)
    if key not in state["screen_enter_times"]:
        state["screen_enter_times"][key] = datetime.now(timezone.utc).isoformat()


def _next_button(
    logger: EventLogger, state: dict, label: str, next_stage: int, key: str
) -> None:
    if st.button(label, type="primary", key=key):
        _log(logger, state, "screen_completed", screen=int(state["stage"]))
        state["stage"] = next_stage
        st.rerun()


# ─── Agent loader (resource-cached across reruns) ────────────────────────────

@st.cache_resource(show_spinner="Preparing decision agent…")
def _load_cached_agent(condition_id: str) -> AgenticHiringDecisionAgent:
    return create_decision_agent(condition=condition_id)


# ─── Individual screens ───────────────────────────────────────────────────────

def _screen_0_welcome(state: dict, condition: Condition, logger: EventLogger) -> None:
    st.header("AI Hiring Decision Assistant — Study Task")
    st.info(
        "This is a fictional research scenario. **Do not use this assistant for real "
        "employment decisions.** All names, companies, and roles are hypothetical."
    )
    st.markdown(
        "You will review a candidate CV for a fictional role. An AI assistant will "
        "provide a recommendation. **The final decision is always yours.**"
    )
    pid_default = str(state.get("participant_id") or st.session_state.get("prolific_pid", ""))
    is_prefilled = bool(pid_default)
    participant_id = st.text_input(
        "Participant ID",
        value=pid_default,
        disabled=is_prefilled,
        help="Automatically filled from your study link." if is_prefilled else "Enter the participant ID provided to you.",
        key="participant_id_input",
    )
    if st.button("Begin task", type="primary", key="begin_task"):
        state["participant_id"] = participant_id.strip() or "pilot_anonymous"
        state["prolific_pid"] = st.session_state.get("prolific_pid", "")
        state["session_start"] = datetime.now(timezone.utc).isoformat()
        logger = restored_logger(condition, state)
        _log(logger, state, "session_started", prolific_pid=state["prolific_pid"])
        state["stage"] = 2
        st.rerun()


def _screen_2_role(
    state: dict, agent: AgenticHiringDecisionAgent, logger: EventLogger
) -> None:
    st.header("Role Description — Summary")
    st.markdown(ROLE_SUMMARY)

    _next_button(logger, state, "Continue to screening policy →", 3, "next_to_policy")


def _screen_3_policy(
    state: dict, agent: AgenticHiringDecisionAgent, logger: EventLogger
) -> None:
    st.header("Screening Policy — Summary")
    st.markdown(POLICY_SUMMARY)
    _next_button(logger, state, "Continue to candidate CV →", 4, "next_to_cv")


def _show_document_with_highlight(
    state: dict,
    agent: AgenticHiringDecisionAgent,
    logger: EventLogger,
    doc_key: str,
    highlight_id: Optional[str] = None,
) -> None:
    """Render a full document, optionally highlighting the cited section.

    When `highlight_id` is set (citation-driven navigation), the matching section
    is shown with a yellow background; all other sections are shown normally.
    """
    _DOC_TITLES = {
        "role_description": "Role Description",
        "screening_policy": "Screening Policy",
        "candidate_cv": "Candidate CV",
    }
    title = _DOC_TITLES.get(doc_key, doc_key.replace("_", " ").title())
    st.header(title)
    if highlight_id:
        st.caption("The highlighted section is the one cited in the recommendation.")

    sections = agent.get_document_sections(doc_key)
    if not sections and doc_key == "candidate_cv":
        st.markdown(CV_MARKDOWN)
    else:
        for section in sections:
            if section.evidence_id == highlight_id:
                st.markdown(
                    f'<div id="cited-section" style="background:#fff3cd;padding:1rem 1.25rem;'
                    f'border-left:5px solid #f0ad4e;border-radius:4px;'
                    f'line-height:1.7;margin:0.5rem 0 1rem">'
                    f'<strong>{section.heading}</strong><br><br>'
                    f'{section.text}'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(f"**{section.heading}**")
                st.write(section.text)

    st.divider()
    from_screen = state.get("doc_view_from", "recommendation")
    back_label = "← Back to recommendation" if from_screen == "recommendation" else "← Back to candidate CV"
    if st.button(back_label, key=f"back_doc_{doc_key}", type="primary"):
        _log(
            logger, state, "document_view_closed",
            document=doc_key,
            highlight_section=highlight_id,
            from_screen=from_screen,
        )
        state["doc_view"] = None
        state["doc_view_from"] = None
        state["highlight_section"] = None
        st.rerun()


def _screen_4_cv(
    state: dict,
    agent: AgenticHiringDecisionAgent,
    agent_state: AgentState,
    logger: EventLogger,
    condition: Condition,
) -> None:
    """Single screen: CV review + assessment preferences (C=1) + AI recommendation + Stage 2 + settledness."""
    # ── Handle doc sub-views ──────────────────────────────────────────────────
    doc_view = state.get("doc_view")
    if doc_view:
        _show_document_with_highlight(
            state, agent, logger, doc_view, state.get("highlight_section")
        )
        return

    # ── CV ────────────────────────────────────────────────────────────────────
    st.header(f"Candidate Application — {CANDIDATE_NAME}")
    st.markdown(CV_MARKDOWN)

    col_role, col_policy, _ = st.columns([1, 1, 2])
    with col_role:
        if st.button("View role description", key="view_role_from_cv", use_container_width=True):
            state["doc_view"] = "role_description"
            state["doc_view_from"] = "cv"
            state["role_full_viewed"] = True
            state["provenance_clicks"] += 1
            _log(logger, state, "full_document_opened",
                 document="role_description", from_screen="cv",
                 provenance_click_count=state["provenance_clicks"])
            st.rerun()
    with col_policy:
        if st.button("View screening policy", key="view_policy_from_cv", use_container_width=True):
            state["doc_view"] = "screening_policy"
            state["doc_view_from"] = "cv"
            state["policy_full_viewed"] = True
            state["provenance_clicks"] += 1
            _log(logger, state, "full_document_opened",
                 document="screening_policy", from_screen="cv",
                 provenance_click_count=state["provenance_clicks"])
            st.rerun()

    st.divider()

    # ── HIC Stage 1: Human Intervention Checkpoint before recommendation ────────
    if condition.hic and not state.get("reco_generated"):
        with st.chat_message("assistant"):
            st.write(hic_stage1_prompt(condition))

        for area in FOCUS_AREAS:
            default = area in state.get("user_focus_areas", [])
            st.checkbox(area, value=default, key=f"focus_{area}")

        free_label = (
            "Anything else you would like me to consider? (optional)"
            if condition.anthropomorphic_cues
            else "Additional area for attention (optional):"
        )
        st.text_area(
            free_label,
            value=state.get("user_focus_text", ""),
            height=80,
            max_chars=500,
            key="hic1_free_text",
            placeholder=(
                "e.g. I want to understand whether the candidate can work independently."
                if condition.anthropomorphic_cues
                else "e.g. focus on evidence of direct recruitment ownership"
            ),
        )

    # ── Generate recommendation button ────────────────────────────────────────
    if not state.get("reco_generated"):
        btn_label = (
            "Continue to recommendation"
            if condition.anthropomorphic_cues
            else "Generate recommendation"
        )
        if st.button(btn_label, type="primary", key="generate_reco_btn"):
            cv_enter_iso = state["screen_enter_times"].get("4")
            cv_dwell_seconds: int | None = None
            if cv_enter_iso:
                try:
                    cv_enter = datetime.fromisoformat(cv_enter_iso)
                    cv_dwell_seconds = round((datetime.now(timezone.utc) - cv_enter).total_seconds())
                except ValueError:
                    pass
            _log(
                logger, state, "candidate_cv_viewed",
                candidate_name=CANDIDATE_NAME,
                cv_dwell_seconds=cv_dwell_seconds,
                role_full_viewed=state.get("role_full_viewed", False),
                policy_full_viewed=state.get("policy_full_viewed", False),
                provenance_clicks=state.get("provenance_clicks", 0),
            )
            if condition.hic:
                collected = [a for a in FOCUS_AREAS if st.session_state.get(f"focus_{a}", False)]
                collected_text = st.session_state.get("hic1_free_text", "").strip()
                state["user_focus_areas"] = collected
                state["user_focus_text"] = collected_text
                focus_parts = list(collected)
                if collected_text:
                    focus_parts.append(collected_text)
                state["user_focus"] = "; ".join(focus_parts)
                state["hic1_completed"] = True
                _log(
                    logger, state, "hic_stage1_completed",
                    hic_stage1_areas=collected,
                    hic_stage1_free_text=collected_text,
                    hic_stage1_combined=state["user_focus"],
                )
            state["reco_generated"] = True
            st.rerun()
        return  # Don't render recommendation until button clicked

    # ── Recommendation ────────────────────────────────────────────────────────
    if agent_state.recommendation_state is None:
        with st.spinner(
            "Reviewing the candidate materials\u2026" if condition.anthropomorphic_cues
            else "Generating assessment\u2026"
        ):
            try:
                agent.apply_stage1_steering(
                    agent_state,
                    state.get("user_focus_areas", []),
                    state.get("user_focus_text", ""),
                )
                agent.generate_recommendation(agent_state)
            except Exception:
                st.error(
                    "The assistant encountered a problem preparing the recommendation. "
                    "Please refresh the page to try again, or notify the researcher "
                    "if the problem persists."
                )
                return

    rec_state = agent_state.recommendation_state
    rendered = rec_state.rendered

    if not state["recommendation_logged"]:
        _log(
            logger, state, "recommendation_presented",
            recommendation=rec_state.recommendation,
            agent_output=rendered.text,
            condition_id=condition.condition_id,
            explainability=condition.explainability,
            anthropomorphic_cues=condition.anthropomorphic_cues,
            hic=condition.hic,
            citation_chips=[s.evidence_id for s in rendered.citation_chips],
        )
        state["recommendation_logged"] = True
        state["ai_recommendation"] = rec_state.recommendation

    with st.chat_message("assistant"):
        if condition.explainability and rendered.citation_chips:
            _render_conversational_with_citations(state, rendered.text, rendered.citation_chips, logger, condition)
        else:
            st.write(rendered.text)

    # ── HIC Stage 2: Human Intervention Checkpoint after recommendation ────────

    if condition.hic and not state.get("stage2_done"):
        has_response = bool(state.get("_challenge_text"))

        if not has_response:
            with st.chat_message("assistant"):
                st.write(hic_stage2_prompt(condition))
        else:
            with st.chat_message("assistant"):
                st.write(state["_challenge_text"])

        select_label = (
            "Would you like to look at something else?"
            if has_response
            else "Select an area to examine:"
        )
        hic2_option = st.selectbox(
            select_label,
            options=HIC_STAGE2_OPTIONS,
            index=None,
            placeholder="Choose an area…",
            key=f"hic2_selectbox_{state.get('hic2_count', 0)}",
        )

        hic2_free_label = (
            "Anything specific you would like me to focus on? (optional)"
            if condition.anthropomorphic_cues
            else "Additional context (optional):"
        )
        hic2_free = st.text_area(
            hic2_free_label,
            height=70,
            max_chars=500,
            key="hic2_free_text",
            placeholder="Optional — add any specific focus or context here.",
        )

        col_examine, col_skip = st.columns([1, 1])
        with col_examine:
            examine_label = "Examine this" if condition.anthropomorphic_cues else "Examine"
            if st.button(examine_label, type="primary", key="submit_hic2_btn", disabled=not hic2_option):
                try:
                    challenge_resp = agent.handle_stage2_challenge(
                        agent_state, hic2_option or "",
                        custom_question=hic2_free.strip(),
                    )
                except Exception:
                    st.error("Could not retrieve a response — please try again.")
                else:
                    state["_challenge_text"] = challenge_resp.response_text
                    state["hic2_option"] = hic2_option
                    state["hic2_count"] = state.get("hic2_count", 0) + 1
                    _log(
                        logger, state, "hic_stage2_submitted",
                        hic_option=hic2_option,
                        hic_free_text=hic2_free.strip(),
                        hic_response=challenge_resp.response_text,
                        cited_sections=[e.evidence_id for e in challenge_resp.cited_sections],
                    )
                    st.rerun()
        with col_skip:
            if st.button("Continue to my decision →", key="hic2_skip_btn"):
                state["stage2_done"] = True
                _log(logger, state, "hic_stage2_skipped")
                st.rerun()

    # ── Judgement Settledness ──────────────────────────────────────────────────
    show_settledness = (
        not condition.hic
        or state.get("stage2_done")
    )
    if show_settledness:
        st.divider()
        st.markdown("**At this point, how settled is your judgement about the recommendation?**")
        st.caption("1 = I still need to examine it further \u00b7 7 = My judgement is fully settled")
        settledness_val = st.select_slider(
            "Judgement settledness",
            options=[1, 2, 3, 4, 5, 6, 7],
            value=state.get("judgement_settledness") or 4,
            key="judgement_settledness_slider",
            label_visibility="collapsed",
        )
        if st.button("Confirm and continue to decision \u2192", type="primary", key="confirm_settledness"):
            state["judgement_settledness"] = int(settledness_val)
            if not state["judgement_settledness_logged"]:
                _log(
                    logger, state, "judgement_settledness_recorded",
                    judgement_settledness=int(settledness_val),
                    recommendation=rec_state.recommendation,
                    provenance_clicks=state.get("provenance_clicks", 0),
                    evidence_inspected=bool(state.get("evidence_inspection_logged")),
                    hic_stage2_explored=bool(state.get("hic2_option")),
                )
                state["judgement_settledness_logged"] = True
            state["stage"] = 7
            st.rerun()




_DOC_ABBREV_CHIP = {
    "role_description": "Role",
    "screening_policy": "Policy",
    "candidate_cv": "CV",
}


def _style_section_refs(text: str, label_map: dict) -> str:
    """Visually highlight Section X.Y references inline (non-clickable styling only)."""

    def _sub(m: re.Match) -> str:
        label = m.group(0)
        if label in label_map:
            return (
                f'<span style="color:#1d4ed8;font-weight:600">{label}</span>'
            )
        return label

    return re.sub(r"Section\s+\d+\.\d+", _sub, text)


def _chip_click(
    state: dict,
    logger: EventLogger,
    chip: EvidenceSection,
    condition: Condition,
) -> None:
    """Log a citation chip click and navigate to the cited document section."""
    state["provenance_clicks"] += 1
    _log(
        logger, state, "citation_clicked",
        participant_id=state.get("participant_id", ""),
        condition_id=condition.condition_id,
        citation_id=chip.evidence_id,
        document_type=chip.document_key,
        section_number=chip.section_label,
        source_screen="recommendation",
        provenance_click_count=state["provenance_clicks"],
    )
    state["doc_view"] = chip.document_key
    state["highlight_section"] = chip.evidence_id
    state["doc_view_from"] = "recommendation"
    st.rerun()


def _render_chip(
    chip: EvidenceSection,
    state: dict,
    logger: EventLogger,
    condition: Condition,
    key_suffix: str = "",
) -> None:
    """Render a single clickable citation chip button."""
    abbr = _DOC_ABBREV_CHIP.get(chip.document_key, chip.document_key[:4].title())
    sec_match = re.search(r"\d+\.\d+", chip.section_label)
    label = f"[{abbr} \u00a7{sec_match.group()}]" if sec_match else f"[{abbr}]"
    if st.button(label, key=f"cite_{chip.evidence_id}{key_suffix}", help=chip.heading):
        _chip_click(state, logger, chip, condition)


def _render_conversational_with_citations(
    state: dict,
    text: str,
    chips: list[EvidenceSection],
    logger: EventLogger,
    condition: Condition,
) -> None:
    """Render recommendation text with citation chips immediately after each cited sentence.

    Splits at sentence boundaries. After each sentence that references a document
    section, the corresponding chips appear directly below it — never as a
    detached evidence list at the bottom of the message.
    """
    if not chips:
        st.write(text)
        return

    label_map = {s.section_label: s for s in chips}
    rendered_ids: set[str] = set()

    # Split at sentence boundaries (. ! ? followed by space and capital letter)
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z])", text.strip())

    pending: list[str] = []

    def _flush_pending() -> None:
        if pending:
            st.markdown(" ".join(pending))
            pending.clear()

    for sentence in sentences:
        refs = list(dict.fromkeys(re.findall(r"Section\s+\d+\.\d+", sentence)))
        sentence_chips = [
            label_map[r]
            for r in refs
            if r in label_map and label_map[r].evidence_id not in rendered_ids
        ]

        if not sentence_chips:
            pending.append(sentence)
            continue

        _flush_pending()

        styled = _style_section_refs(sentence, label_map)
        st.markdown(styled, unsafe_allow_html=True)

        max_cols = min(len(sentence_chips), 4)
        chip_cols = st.columns(max_cols)
        for i, chip in enumerate(sentence_chips):
            with chip_cols[i % max_cols]:
                _render_chip(chip, state, logger, condition)
            rendered_ids.add(chip.evidence_id)

    _flush_pending()

    # Overflow: chips not matched to any sentence (edge case)
    overflow = [c for c in chips if c.evidence_id not in rendered_ids]
    if overflow:
        max_ocols = min(len(overflow), 4)
        ocols = st.columns(max_ocols)
        for i, chip in enumerate(overflow):
            with ocols[i % max_ocols]:
                _render_chip(chip, state, logger, condition, key_suffix="_ov")




def _screen_7_decision(
    state: dict, condition: Condition, logger: EventLogger
) -> None:
    ai_recommendation = state.get("ai_recommendation", BASE_RECOMMENDATION)
    st.header("Final Human Decision")
    st.write("Select the screening action you judge appropriate.")
    with st.form("final_decision_form"):
        decision = st.radio(
            "Final screening action",
            RECOMMENDATION_ACTIONS,
            index=None,
            key="final_screening_action",
        )
        hold_reasons: list[str] = []
        if decision == "Hold for further review":
            st.markdown("**Before holding:** select at least one unresolved issue:")
            for opt in HOLD_UNRESOLVED_OPTIONS:
                if st.checkbox(opt, key=f"hold_{opt}"):
                    hold_reasons.append(opt)
        submitted = st.form_submit_button("Submit final decision", type="primary")
    if submitted:
        if decision is None:
            st.error("Please select a screening action before submitting.")
            return
        if decision == "Hold for further review" and not hold_reasons:
            st.error("Please select at least one unresolved issue to justify holding.")
            return
        state["decision"] = decision
        state["hold_reasons"] = hold_reasons
        _log(
            logger, state, "final_decision_recorded",
            recommendation=ai_recommendation,
            final_human_decision=decision,
            recommendation_followed=decision == ai_recommendation,
            hold_reasons=hold_reasons,
            judgement_settledness=state.get("judgement_settledness"),
        )
        if not state.get("session_saved"):
            with st.spinner("Saving session data…"):
                saved = _save_session_to_github(state, condition, logger)
            state["session_saved"] = True
            if not saved:
                st.warning(
                    "Session data could not be saved to GitHub — please notify the researcher. "
                    "Your local log has been retained."
                )
        state["stage"] = 9
        st.rerun()


def _screen_9_complete(state: dict) -> None:
    st.markdown(
        "<div class='completion-card'>"
        "<h2>Task complete &#x2713;</h2>"
        "<p>Thank you for participating in this study.</p>"
        "</div>",
        unsafe_allow_html=True,
    )
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Your decision", state.get("decision", "—"))
    with col2:
        st.metric("AI recommendation", state.get("ai_recommendation", "—"))
    st.caption(f"Session reference: {state.get('session_id', '—')}")
    st.divider()
    if st.session_state.get("has_return_url"):
        st.info("Click below to return to your survey and complete the questionnaire.")
        if st.button("Return to survey \u2192", type="primary", key="return_to_survey"):
            back_to_survey(done_flag=True)
    else:
        st.info("Please return to your survey tab and continue with the questionnaire.")


# ─── Entry point ──────────────────────────────────────────────────────────────

def run(condition_id: str) -> None:
    """Render one condition's UI over the shared case materials."""
    condition = get_condition(condition_id)

    st.set_page_config(
        page_title="AI Hiring Decision Assistant",
        page_icon="🔎",
        layout="centered",
        initial_sidebar_state="collapsed",
    )
    apply_anthrokit_theme(st)
    # Allow chat bubbles to fill the 860 px reading column set by theme.py
    st.markdown(
        """
        <style>
        div[data-testid="stChatMessageContent"] { max-width: 100% !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Qualtrics / Prolific gate
    _read_qualtrics_params()
    _prolific_gate()
    st.session_state.has_return_url = bool(st.session_state.get("return_raw", ""))

    # Per-condition session state
    key = _state_key(condition)
    if key not in st.session_state:
        st.session_state[key] = _initial_state()
    state: dict = st.session_state[key]

    # Propagate Prolific ID into state for logging
    if not state.get("prolific_pid"):
        state["prolific_pid"] = st.session_state.get("prolific_pid", "")

    logger = restored_logger(condition, state)
    show_study_banner(st)

    stage = int(state["stage"])
    _record_screen_entry(state, stage)
    show_study_progress(st, stage)

    # Load the single shared agent (cached across reruns)
    agent = _load_cached_agent(condition_id)

    # Initialise the AgentState once per session
    if "agent_state" not in state or state["agent_state"] is None:
        participant_id = state.get("participant_id") or st.session_state.get("prolific_pid", "anon")
        state["agent_state"] = agent.start_assessment(participant_id, "northstar_hiring_case")
    agent_state: AgentState = state["agent_state"]

    if stage == 0:
        _screen_0_welcome(state, condition, logger)
    elif stage == 1:
        state["stage"] = 2
        st.rerun()
    elif stage == 2:
        _screen_2_role(state, agent, logger)
    elif stage == 3:
        _screen_3_policy(state, agent, logger)
    elif stage == 4:
        _screen_4_cv(state, agent, agent_state, logger, condition)
    elif stage == 5:
        state["stage"] = 4
        st.rerun()
    elif stage == 6:
        state["stage"] = 4
        st.rerun()
    elif stage == 7:
        _screen_7_decision(state, condition, logger)
    elif stage == 9:
        _screen_9_complete(state)

