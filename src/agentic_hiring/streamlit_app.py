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
    CHALLENGE_AREAS,
    post_recommendation_prompt,
    RECOMMENDATION_ACTIONS,
    BASE_RECOMMENDATION,
    get_condition,
    steering_prompt,
)
from .decision_agent import AgenticHiringDecisionAgent, create_decision_agent
from .logger import EventLogger, restored_logger
from .schemas import AgentState, EvidenceSection
from .theme import apply_anthrokit_theme, show_study_banner

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

*No formal title as recruiter, talent partner, or talent specialist. No explicit
statement of end-to-end structured recruitment ownership.*
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
        "mixed_initiative_control_cues": condition.mixed_initiative_control_cues,
        "session_start": state.get("session_start", ""),
        "candidate_name": CANDIDATE_NAME,
        "steering": {
            "user_focus_areas": state.get("user_focus_areas", []),
            "user_focus_text": state.get("user_focus_text", ""),
            "user_focus": state.get("user_focus", ""),
            "post_reco_option": state.get("post_reco_option", ""),
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
        # Pre-recommendation steering (C=1)
        "user_steering_completed": False,
        "user_focus_areas": [],
        "user_focus_text": "",
        "user_focus": "",
        # Post-recommendation challenge (C=1)
        "post_reco_option": "",
        "post_reco_logged": False,
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
    if not os.getenv("OPENAI_API_KEY"):
        st.warning(
            "Development fallback active — live RAG is disabled. "
            "Set `OPENAI_API_KEY` and `AGENTIC_REQUIRE_LIVE_RAG=true` before data collection."
        )
    pid_default = str(state.get("participant_id") or st.session_state.get("prolific_pid", ""))
    participant_id = st.text_input(
        "Participant ID (pre-filled from Prolific — do not change unless asked)",
        value=pid_default,
        key="participant_id_input",
    )
    if st.button("Begin task", type="primary", key="begin_task"):
        state["participant_id"] = participant_id.strip() or "pilot_anonymous"
        state["prolific_pid"] = st.session_state.get("prolific_pid", "")
        state["session_start"] = datetime.now(timezone.utc).isoformat()
        logger = restored_logger(condition, state)
        _log(logger, state, "session_started", prolific_pid=state["prolific_pid"])
        state["stage"] = 1
        st.rerun()


def _screen_1_company(
    state: dict, agent: AgenticHiringDecisionAgent, logger: EventLogger
) -> None:
    sections = agent.get_document_sections("company_context")
    title = sections[0].document_title if sections else "Company Context"
    st.header(title)
    for section in sections:
        st.markdown(f"**{section.heading}**")
        st.write(section.text)
    _next_button(logger, state, "Continue to role description →", 2, "next_to_role")


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


def _show_full_doc_view(
    state: dict, agent: AgenticHiringDecisionAgent, logger: EventLogger, doc_key: str
) -> None:
    """Render a full knowledge-base document with a back button."""
    titles = {
        "role_description": "Role Description — Full Document",
        "screening_policy": "Screening Policy — Full Document",
    }
    st.header(titles.get(doc_key, doc_key))
    sections = agent.get_document_sections(doc_key)
    for section in sections:
        st.markdown(f"**{section.heading}**")
        st.write(section.text)
    st.divider()
    back_label = (
        "← Back to candidate CV"
        if state.get("doc_view_from") == "cv"
        else "← Back to recommendation"
    )
    if st.button(back_label, key=f"back_from_{doc_key}"):
        _log(logger, state, "full_document_closed",
             document=doc_key, from_screen=state.get("doc_view_from"))
        state["doc_view"] = None
        state["doc_view_from"] = None
        st.rerun()


def _screen_4_cv(
    state: dict, agent: AgenticHiringDecisionAgent, logger: EventLogger, condition: Condition
) -> None:
    # Sub-view: full document opened from CV screen
    doc_view = state.get("doc_view")
    if doc_view in ("role_description", "screening_policy"):
        _show_full_doc_view(state, agent, logger, doc_view)
        return

    st.header(f"Candidate Application — {CANDIDATE_NAME}")
    st.caption(
        "Read the candidate's CV below. You may consult the role description or screening "
        "policy at any time using the reference buttons. When you are ready, request the "
        "AI's recommendation."
    )
    st.divider()
    st.markdown(CV_MARKDOWN)
    st.divider()

    next_label = (
        "Set my priorities before seeing the recommendation →"
        if condition.mixed_initiative_control_cues
        else "Request AI recommendation →"
    )
    next_screen = 5 if condition.mixed_initiative_control_cues else 6

    if st.button(next_label, type="primary", key="proceed_from_cv"):
        # Compute how long the recruiter spent reading the CV
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
        state["stage"] = next_screen
        st.rerun()

    st.markdown("**Reference documents:**")
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


def _screen_5_steering(
    state: dict, logger: EventLogger, condition: Condition
) -> None:
    """Pre-recommendation steering screen (C=1 conditions only)."""
    st.header("Set Your Priorities")
    st.markdown(steering_prompt(condition))
    selected_areas = st.multiselect(
        "Select the areas you want the AI to focus on (choose all that apply):",
        options=FOCUS_AREAS,
        default=state.get("user_focus_areas", []),
        key="steering_focus_areas",
    )
    free_text = st.text_area(
        "Add any specific priorities or concerns in your own words (optional):",
        value=state.get("user_focus_text", ""),
        height=100,
        max_chars=500,
        key="steering_free_text",
        placeholder="e.g. I want to understand whether the candidate can work independently.",
    )
    if st.button("Send priorities and get recommendation →", type="primary", key="submit_steering"):
        state["user_focus_areas"] = selected_areas
        state["user_focus_text"] = free_text.strip()
        focus_parts = list(selected_areas)
        if free_text.strip():
            focus_parts.append(free_text.strip())
        state["user_focus"] = "; ".join(focus_parts)
        state["user_steering_completed"] = True
        _log(
            logger, state, "pre_recommendation_steering",
            user_focus_areas=selected_areas,
            user_focus_text=free_text.strip(),
            user_focus=state["user_focus"],
        )
        state["stage"] = 6
        st.rerun()


def _render_citation_chips(
    state: dict,
    chips: list[EvidenceSection],
    logger: EventLogger,
) -> None:
    """Render clickable citation chips for EvidenceSection objects cited in the recommendation."""
    if not chips:
        return
    st.caption("Evidence cited — click to inspect the source section:")
    cols = st.columns(min(len(chips), 6))
    for idx, section in enumerate(chips[:6]):
        with cols[idx]:
            if st.button(
                section.section_label,
                key=f"cite_{section.evidence_id}",
                use_container_width=True,
            ):
                state["doc_view"] = section.evidence_id
                state["doc_view_from"] = "recommendation"
                state["provenance_clicks"] += 1
                if section.document_key == "role_description":
                    state["role_full_viewed"] = True
                elif section.document_key == "screening_policy":
                    state["policy_full_viewed"] = True
                _log(
                    logger, state, "citation_chip_clicked",
                    evidence_id=section.evidence_id,
                    section_label=section.section_label,
                    document=section.document_key,
                    provenance_click_count=state["provenance_clicks"],
                )
                st.rerun()


def _show_section_view(
    state: dict, section: EvidenceSection, logger: EventLogger
) -> None:
    """Render a single cited evidence section with a back button."""
    st.header(section.heading)
    st.caption(f"{section.document_title} · {section.section_label}")
    st.divider()
    st.write(section.text)
    st.divider()
    if st.button("← Back to recommendation", key=f"back_from_section_{section.evidence_id}"):
        _log(logger, state, "section_view_closed",
             evidence_id=section.evidence_id, section=section.section_label)
        state["doc_view"] = None
        state["doc_view_from"] = None
        st.rerun()


def _screen_6_recommendation(
    state: dict,
    condition: Condition,
    agent: AgenticHiringDecisionAgent,
    agent_state: AgentState,
    logger: EventLogger,
) -> None:
    # Sub-view: individual cited section opened from citation chip
    doc_view = state.get("doc_view")
    if doc_view and doc_view not in ("role_description", "screening_policy"):
        section = agent.get_section(doc_view)
        if section:
            _show_section_view(state, section, logger)
            return
    if doc_view in ("role_description", "screening_policy"):
        _show_full_doc_view(state, agent, logger, doc_view)
        return

    st.header("AI Recommendation")

    # Generate recommendation once and cache in session state
    if agent_state.recommendation_state is None:
        with st.spinner("The AI is reviewing the candidate materials\u2026"):
            agent.apply_stage1_steering(
                agent_state,
                state.get("user_focus_areas", []),
                state.get("user_focus_text", ""),
            )
            agent.generate_recommendation(agent_state)

    rec_state = agent_state.recommendation_state
    rendered = rec_state.rendered

    # Log once
    if not state["recommendation_logged"]:
        _log(
            logger, state, "recommendation_presented",
            recommendation=rec_state.recommendation,
            agent_output=rendered.text,
            condition_id=condition.condition_id,
            explainability=condition.explainability,
            anthropomorphic_cues=condition.anthropomorphic_cues,
            mixed_initiative_control_cues=condition.mixed_initiative_control_cues,
            citation_chips=[s.evidence_id for s in rendered.citation_chips],
        )
        state["recommendation_logged"] = True
        state["ai_recommendation"] = rec_state.recommendation

    with st.chat_message("assistant"):
        st.write(rendered.text)
        # Citation chips inside bubble (High Explainability conditions)
        if condition.explainability:
            _render_citation_chips(state, rendered.citation_chips, logger)

    # ── Stage 2: Post-recommendation challenge (C=1 only) ────────────────────
    if condition.mixed_initiative_control_cues:
        st.divider()
        st.info(post_recommendation_prompt(condition))

        challenge_key = "post_reco_selectbox"
        post_option = st.selectbox(
            "Select an aspect to examine:",
            options=["— No further exploration needed —"] + CHALLENGE_AREAS,
            index=0,
            key=challenge_key,
        )

        if post_option and post_option != "— No further exploration needed —":
            custom_q = ""
            if post_option == "Ask a custom question":
                custom_q = st.text_area(
                    "Enter your question:",
                    height=80,
                    max_chars=500,
                    key="custom_challenge_input",
                    placeholder="e.g. How does the candidate compare to a typical applicant for this role?",
                )

            cache_key = f"challenge_{post_option}_{custom_q[:30]}"
            if state.get("post_reco_option") != cache_key:
                state["post_reco_option"] = cache_key
                challenge_resp = agent.handle_stage2_challenge(
                    agent_state, post_option, custom_question=custom_q
                )
                state["_challenge_text"] = challenge_resp.response_text
                if not state["post_reco_logged"]:
                    _log(
                        logger, state, "post_recommendation_steering",
                        option=post_option,
                        custom_question=custom_q,
                        follow_up=challenge_resp.response_text,
                    )
                    state["post_reco_logged"] = True

            if state.get("_challenge_text"):
                with st.chat_message("assistant"):
                    st.write(state["_challenge_text"])

    # ── Judgement Settledness scale ───────────────────────────────────────────
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
                post_reco_explored=bool(state.get("post_reco_logged")),
            )
            state["judgement_settledness_logged"] = True
        state["stage"] = 7
        st.rerun()


def _screen_7_decision(
    state: dict, logger: EventLogger
) -> None:
    ai_recommendation = state.get("ai_recommendation", BASE_RECOMMENDATION)
    st.header("Final Human Decision")
    st.write(
        "Select the screening action you judge appropriate. "
        "**Your decision may differ from the AI recommendation.** "
        f"The AI recommended: *{ai_recommendation}*."
    )
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
        state["stage"] = 8
        st.rerun()


def _screen_8_questionnaire(
    state: dict, condition: Condition, logger: EventLogger
) -> None:
    st.header("Study Questionnaire")
    st.write("Please answer the following questions about your experience.")
    scale = ["1 — Strongly disagree", "2", "3", "4", "5 — Strongly agree"]
    with st.form("questionnaire_form"):
        st.subheader("Agency and control")
        agency_responses: dict = {}
        for item in AGENCY_ITEMS:
            val = st.radio(item, scale, index=None, key=f"agency_{item[:30]}")
            agency_responses[item] = val

        st.subheader("Reliance")
        reliance_responses: dict = {}
        for item in RELIANCE_ITEMS:
            val = st.radio(item, scale, index=None, key=f"reliance_{item[:30]}")
            reliance_responses[item] = val

        submitted = st.form_submit_button("Submit responses", type="primary")

    if submitted:
        all_r = {**agency_responses, **reliance_responses}
        unanswered = [k for k, v in all_r.items() if v is None]
        if unanswered:
            st.error(
                f"Please answer all questions before submitting ({len(unanswered)} remaining)."
            )
            return
        state["questionnaire_responses"] = {
            "agency": agency_responses,
            "reliance": reliance_responses,
        }
        _log(
            logger, state, "questionnaire_completed",
            agency_responses=agency_responses,
            reliance_responses=reliance_responses,
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
    st.success("Task complete. Thank you for participating.")
    st.write(
        f"Your decision: **{state.get('decision', '—')}**  \n"
        f"AI recommendation: **{state.get('ai_recommendation', '—')}**"
    )
    st.caption(f"Session ID: `{state.get('session_id', '—')}`")
    if st.session_state.get("has_return_url"):
        if st.button("Return to survey →", type="primary", key="return_to_survey"):
            back_to_survey(done_flag=True)
    else:
        st.info("Please return to your survey and continue.")


# ─── Entry point ──────────────────────────────────────────────────────────────

def run(condition_id: str) -> None:
    """Render one condition's UI over the shared case materials."""
    condition = get_condition(condition_id)

    st.set_page_config(
        page_title="AI Hiring Decision Assistant",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    apply_anthrokit_theme(st)

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
        _screen_1_company(state, agent, logger)
    elif stage == 2:
        _screen_2_role(state, agent, logger)
    elif stage == 3:
        _screen_3_policy(state, agent, logger)
    elif stage == 4:
        _screen_4_cv(state, agent, logger, condition)
    elif stage == 5:
        if condition.mixed_initiative_control_cues:
            _screen_5_steering(state, logger, condition)
        else:
            state["stage"] = 6
            st.rerun()
    elif stage == 6:
        _screen_6_recommendation(state, condition, agent, agent_state, logger)
    elif stage == 7:
        _screen_7_decision(state, logger)
    elif stage == 8:
        _screen_8_questionnaire(state, condition, logger)
    elif stage == 9:
        _screen_9_complete(state)

