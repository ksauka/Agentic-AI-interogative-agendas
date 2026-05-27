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


_SCREEN_NAMES = {
    0: "welcome",
    2: "role_summary",
    3: "policy_summary",
    4: "candidate_cv_and_recommendation",
    7: "final_decision",
    9: "complete",
}

# ─── Fixed study case ─────────────────────────────────────────────────────────

CANDIDATE_NAME = "Yuna Suvh"

CV_MARKDOWN = """\
# Yuna Suvh
**People and Operations Coordinator**
Amsterdam, Netherlands · y.suvh@example.com

---

## Professional Summary

Operations and coordination professional with experience supporting people-related
workflows in fast-moving business environments. Has worked on candidate scheduling,
hiring follow-ups, onboarding preparation, stakeholder communication, and internal
process tracking. Comfortable maintaining structured records and supporting hiring
managers, but has not held independent ownership of recruitment screening decisions,
strategic talent planning, or final candidate evaluation.

---

## Work Experience

### People and Operations Coordinator  -  Saukala Global
*March 2022 – present · Amsterdam, Netherlands*

- Coordinated candidate scheduling, interview follow-ups, and communication between
  hiring managers and applicants across several open roles
- Maintained internal tracking sheets for candidate progress, interview stages,
  missing feedback, and follow-up actions
- Supported preparation of structured interview packs, role handover notes, and
  evaluation templates for hiring managers
- Flagged incomplete candidate information and delayed feedback to line managers,
  but did not independently assess candidate suitability or make screening
  recommendations
- Assisted with onboarding preparation after hiring decisions had already been made
- Improved internal follow-up processes for open roles by reducing missed
  communication steps and clarifying who needed to respond at each stage
- Worked mainly in an operational support role rather than a formal recruiter,
  talent partner, or strategic hiring role

### Project and Client Support Associate  -  Suvion Digital
*July 2019 – February 2022 · Rotterdam, Netherlands*

- Managed communication across client, operations, and delivery teams in a growing SME
- Tracked project stages, deadlines, and action items using structured internal
  workflows
- Prepared meeting summaries, follow-up records, and stakeholder updates for
  project leads
- Assisted with shortlisting external contractors for project support roles by
  checking availability, basic requirements, and documentation completeness
- Did not make final contractor selection decisions and did not own structured
  candidate evaluation

---

## Education

**BSc in Business Administration**  -  Bazeley Bridge Metropolitan University, 2019

---

## Skills

Stakeholder coordination · Workflow documentation · Process tracking ·
Cross-functional communication · Scheduling and follow-up · Operational support ·
Onboarding preparation · Spreadsheet tracking · Basic ATS exposure ·
Candidate communication support · Interview coordination support

---
"""

ROLE_SUMMARY = """\
**Role:** Strategic Talent Operations Partner
**Organisation:** Northstar Health Analytics
**Location:** Amsterdam, Netherlands (hybrid)
**Reports to:** Head of People Operations

---

**What this role involves**

This is a full-cycle talent operations role at a growing health analytics firm. The person in this role will own the end-to-end candidate journey for multiple open positions simultaneously: coordinating screening, scheduling interviews, communicating with hiring managers, and maintaining accurate candidate records. The role requires both operational reliability and sound judgement about candidate fit.

**Key responsibilities**

- Lead structured, multi-stakeholder hiring processes for technical and operational vacancies
- Apply the firm's internal screening criteria to make or recommend progression decisions on candidates
- Serve as the primary point of contact between hiring managers and candidates throughout each process
- Maintain candidate tracking records and flag delays or gaps to relevant stakeholders
- Support onboarding coordination once progression decisions are made

**Requirements**

| Requirement | Type |
|---|---|
| Structured process coordination across multiple stakeholders and tracking records | **Required** |
| Screening judgement: applying defined criteria to decide or recommend candidate outcomes | **Required** |
| Communication management between hiring managers and candidates | **Required** |
| Direct end-to-end recruitment or talent screening experience in a fast-growing organisation | Preferred |
| Formal recruiter or talent specialist job title | Preferred (not mandatory) |

**Context for screening**

The role sits inside a 60-person and growing firm. The successful candidate must be comfortable making calls independently, not only supporting someone else's decisions. Exact title match is not required if equivalent capability can be demonstrated.
"""

POLICY_SUMMARY = """\
**Recruiter Screening Policy: Key Rules and Decision Framework**

This policy governs how screeners at Northstar Health Analytics should assess and progress candidates. It sets the standards for evidence use, experience equivalence, and decision authority.

---

**1. Evidence rule**
All screening recommendations must be grounded in four sources: (a) the company context, (b) the role description, (c) the screening policy itself, and (d) evidence present in the candidate's CV. Screeners should not reject or advance candidates based on assumptions or information not supported by these sources.

**2. Equivalent experience rule**
A candidate who lacks the exact job title or formal credential but demonstrates equivalent capability through adjacent experience may satisfy a required qualification. Screeners must assess whether the underlying competency is visible, not merely whether the formal label is present. Coordination, evaluation support, and stakeholder management work can substitute for a direct recruitment title where the skills are clearly demonstrated.

**3. No exact-match rejection (Section 7.2)**
Candidates may not be screened out solely because their CV does not use the same terminology as the role description. If a candidate's experience maps to the required capability, the absence of the exact phrase or title is not a valid basis for rejection.

**4. Adjacent experience rule (Section 7.4)**
Candidates operating in roles adjacent to talent operations at increasing levels of responsibility are eligible for progression under this policy, even if they have not held a formal recruiter title. Trajectory and capability matter; title equivalence does not.

**5. Uncertainty rule**
Where evidence in the CV is ambiguous or incomplete, screeners must decide whether the uncertainty is best resolved through: (a) a structured interview to test the specific gap, (b) a hold pending further evidence, or (c) non-progression where the gap is material and cannot be tested at interview. Uncertainty alone is not a sufficient basis for rejection if the evidence gap concerns something an interview can address.

**6. Decision authority**
The final screening decision rests with the human recruiter. AI-generated recommendations are advisory only. The recruiter is responsible for the outcome.
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

    st.markdown(
        """
        <style>
        .prolific-card {
            background: #ffffff;
            border: 1px solid #dee2e6;
            border-top: 5px solid #007bff;
            border-radius: 10px;
            padding: 2.5rem 2.8rem;
            max-width: 620px;
            margin: 3rem auto 0;
            box-shadow: 0 4px 18px rgba(0,123,255,0.10);
        }
        .prolific-card h2 {
            color: #1a1a2e;
            font-size: 1.5rem;
            font-weight: 700;
            margin-bottom: 0.35rem;
        }
        .prolific-card p {
            color: #495057;
            font-size: 1rem;
            margin-bottom: 1.5rem;
            line-height: 1.6;
        }
        </style>
        <div class="prolific-card">
            <h2>Welcome to the Study Task</h2>
            <p><strong>Please enter your Prolific ID below to begin.</strong><br>
            Your ID links your interactions to your survey responses and is required before the task starts.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown("**Prolific ID**")
        prolific_input = st.text_input(
            "Prolific ID",
            placeholder="e.g., 5f8e3c2a1b9d4e6f7a8b9c0d",
            help="This links your interactions to your survey responses.",
            key="prolific_id_input",
            label_visibility="collapsed",
        )
        if st.button("Begin study task", type="primary", key="prolific_continue", use_container_width=True):
            if prolific_input.strip():
                st.session_state.prolific_pid = prolific_input.strip()
                st.session_state.pid = prolific_input.strip()
                st.rerun()
            else:
                st.error("Please enter your Prolific ID before continuing.")
    st.stop()


# ─── GitHub session saving ────────────────────────────────────────────────────


def _get_github_token() -> Optional[str]:
    token = None
    try:
        token = st.secrets.get("GITHUB_TOKEN") or st.secrets.get("GITHUB_DATA_TOKEN")
    except Exception:
        pass
    if not token:
        token = os.getenv("GITHUB_TOKEN") or os.getenv("GITHUB_DATA_TOKEN")
    return token


def _get_github_repo() -> Optional[str]:
    repo = None
    try:
        repo = st.secrets.get("GITHUB_REPO") or st.secrets.get("GITHUB_DATA_REPO")
    except Exception:
        pass
    if not repo:
        repo = os.getenv("GITHUB_REPO") or os.getenv("GITHUB_DATA_REPO")
    return repo


def _save_session_to_github(state: dict, condition: Condition, logger: EventLogger) -> bool:
    """Attach completion metadata to logger and push session to GitHub."""
    token = _get_github_token()
    repo = _get_github_repo()
    citations_shown = state.get("citations_shown", [])
    citations_clicked = state.get("citations_clicked", [])
    unique_clicked = len(set(citations_clicked))
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
            "hic_stage2_shown": state.get("hic_stage2_shown", False),
            "hic_stage2_used": state.get("hic_stage2_used", False),
            "hic_stage2_skip_latency_seconds": state.get("hic_stage2_skip_latency_seconds"),
        },
        "recommendation_change": {
            "recommendation_base": state.get("recommendation_base", BASE_RECOMMENDATION),
            "recommendation_final": state.get("recommendation_final", state.get("ai_recommendation", "")),
            "recommendation_changed_by_hic": state.get("recommendation_changed_by_hic", False),
            "hic_triggered_hold": state.get("hic_triggered_hold", False),
            "hic_uncertain_areas_selected": state.get("hic_uncertain_areas_selected", []),
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
        "recommendation_dwell_seconds": state.get("recommendation_dwell_seconds"),
        "time_from_recommendation_to_final_decision_seconds": state.get("time_from_recommendation_to_final_decision_seconds"),
        "time_from_judgement_settledness_to_final_decision_seconds": state.get("time_from_judgement_settledness_to_final_decision_seconds"),
        "provenance_clicks": state.get("provenance_clicks", 0),
        "citation_evidence_inspected": bool(unique_clicked > 0),
        "citation_click_count": int(state.get("citation_click_count", len(citations_clicked))),
        "unique_citations_clicked": unique_clicked,
        "cited_sections_viewed": state.get("cited_sections_viewed", []),
        "citation_view_dwell_seconds_total": state.get("citation_view_dwell_seconds_total", 0.0),
        "citations_shown": citations_shown,
        "citations_clicked": citations_clicked,
        "role_full_viewed": state.get("role_full_viewed", False),
        "policy_full_viewed": state.get("policy_full_viewed", False),
        "full_document_inspected": bool(state.get("role_full_viewed", False) or state.get("policy_full_viewed", False)),
        "screen_entry_times": state.get("screen_entry_times", state.get("screen_enter_times", {})),
        "screen_dwell_seconds": state.get("screen_dwell_seconds", {}),
        "questionnaire": state.get("questionnaire_responses", {}),
        "qualtrics_returned": bool(st.session_state.get("has_return_url", False)),
        "survey_linkage_id": state.get("session_id", "") or state.get("prolific_pid", ""),
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
        "hic_stage2_shown": False,
        "hic_stage2_shown_at": None,
        "hic_stage2_used": False,
        "hic_stage2_skip_latency_seconds": None,
        "reco_generated": False,
        "recommendation_presented_at": None,
        "recommendation_dwell_seconds": None,
        "recommendation_base": BASE_RECOMMENDATION,
        "recommendation_final": "",
        "recommendation_changed_by_hic": False,
        "hic_triggered_hold": False,
        "hic_uncertain_areas_selected": [],
        # Judgement settledness (shown after recommendation and any Stage 2 challenge)
        "judgement_settledness": None,
        "judgement_settledness_logged": False,
        "judgement_settledness_at": None,
        "final_decision_at": None,
        # Logging sentinels
        "recommendation_logged": False,
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
        "citations_shown": [],
        "citations_clicked": [],
        "citation_click_count": 0,
        "unique_citations_clicked": 0,
        "cited_sections_viewed": [],
        "citation_open_times": {},
        "citation_view_dwell_seconds_total": 0.0,
        "citation_evidence_inspected": False,
        "full_document_inspected": False,
        # Timing
        "screen_entry_times": {},
        "screen_dwell_seconds": {},
        "current_screen": "",
        "doc_view_opened_at": None,
        # Document navigation (full-doc sub-views)
        "doc_view": None,
        "doc_view_from": None,
        # Questionnaire
        "questionnaire_responses": {},
    }




def _log(logger: EventLogger, state: dict, event_type: str, **fields) -> None:
    logger.log(event_type, **fields)
    state["turn_id"] = logger.turn_id


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _seconds_between(start_iso: Optional[str], end_iso: Optional[str] = None) -> Optional[float]:
    if not start_iso:
        return None
    try:
        start = datetime.fromisoformat(start_iso)
        end = datetime.fromisoformat(end_iso) if end_iso else datetime.now(timezone.utc)
        return round((end - start).total_seconds(), 2)
    except (TypeError, ValueError):
        return None


def _screen_name(screen: int) -> str:
    return _SCREEN_NAMES.get(screen, f"screen_{screen}")


def _record_screen_entry(state: dict, screen: int) -> None:
    # Backward-compat for older in-session state keys.
    if "screen_entry_times" not in state:
        state["screen_entry_times"] = state.get("screen_enter_times", {})
    key = str(screen)
    state["current_screen"] = _screen_name(screen)
    if key not in state["screen_entry_times"]:
        state["screen_entry_times"][key] = _now_iso()


def _finalize_screen_dwell(state: dict, screen: int) -> Optional[float]:
    entry = state.get("screen_entry_times", {}).get(str(screen))
    dwell = _seconds_between(entry)
    if dwell is None:
        return None
    screen_name = _screen_name(screen)
    acc = state.setdefault("screen_dwell_seconds", {})
    acc[screen_name] = round(float(acc.get(screen_name, 0.0)) + dwell, 2)
    return dwell


def _next_button(
    logger: EventLogger, state: dict, label: str, next_stage: int, key: str
) -> None:
    if st.button(label, type="primary", key=key):
        current = int(state["stage"])
        dwell = _finalize_screen_dwell(state, current)
        _log(
            logger, state, "screen_completed",
            screen=current,
            screen_name=_screen_name(current),
            screen_dwell_seconds=dwell,
        )
        state["stage"] = next_stage
        st.rerun()


# ─── Agent loader (resource-cached across reruns) ────────────────────────────

@st.cache_resource(show_spinner="Preparing decision agent…")
def _load_cached_agent(condition_id: str) -> AgenticHiringDecisionAgent:
    return create_decision_agent(condition=condition_id)


# ─── Individual screens ───────────────────────────────────────────────────────

def _screen_0_welcome(state: dict, condition: Condition, logger: EventLogger) -> None:
    st.header("AI Hiring Decision Assistant: Study Task")
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
    st.header("Role Description")
    st.markdown(ROLE_SUMMARY)

    _next_button(logger, state, "Continue to screening policy", 3, "next_to_policy")


def _screen_3_policy(
    state: dict, agent: AgenticHiringDecisionAgent, logger: EventLogger
) -> None:
    st.header("Screening Policy")
    st.markdown(POLICY_SUMMARY)
    _next_button(logger, state, "Continue to candidate CV", 4, "next_to_cv")


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
    back_label = "Back to recommendation" if from_screen == "recommendation" else "Back to candidate CV"
    if st.button(back_label, key=f"back_doc_{doc_key}", type="primary"):
        dwell = _seconds_between(state.get("doc_view_opened_at"))
        _log(
            logger, state, "document_view_closed",
            document=doc_key,
            highlight_section=highlight_id,
            from_screen=from_screen,
            dwell_seconds=dwell,
        )
        if highlight_id and from_screen == "recommendation":
            if dwell is not None:
                state["citation_view_dwell_seconds_total"] = round(
                    float(state.get("citation_view_dwell_seconds_total", 0.0)) + dwell, 2
                )
            seen = set(state.get("cited_sections_viewed", []))
            seen.add(highlight_id)
            state["cited_sections_viewed"] = list(seen)
            state["citation_evidence_inspected"] = True
            _log(
                logger, state, "citation_view_closed",
                citation_id=highlight_id,
                document=doc_key,
                dwell_seconds=dwell,
            )
        state["doc_view"] = None
        state["doc_view_from"] = None
        state["highlight_section"] = None
        state["doc_view_opened_at"] = None
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
    st.header(f"Candidate Application: {CANDIDATE_NAME}")
    st.markdown(CV_MARKDOWN)

    col_role, col_policy, _ = st.columns([1, 1, 2])
    with col_role:
        if st.button("View role description", key="view_role_from_cv", use_container_width=True):
            state["doc_view"] = "role_description"
            state["doc_view_from"] = "cv"
            state["doc_view_opened_at"] = _now_iso()
            state["role_full_viewed"] = True
            state["full_document_inspected"] = True
            state["provenance_clicks"] += 1
            _log(logger, state, "full_document_opened",
                 document="role_description", from_screen="cv",
                 provenance_click_count=state["provenance_clicks"])
            st.rerun()
    with col_policy:
        if st.button("View screening policy", key="view_policy_from_cv", use_container_width=True):
            state["doc_view"] = "screening_policy"
            state["doc_view_from"] = "cv"
            state["doc_view_opened_at"] = _now_iso()
            state["policy_full_viewed"] = True
            state["full_document_inspected"] = True
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
        citation_ids = [s.evidence_id for s in rendered.citation_chips]
        state["citations_shown"] = citation_ids
        state["recommendation_presented_at"] = _now_iso()
        state["recommendation_final"] = rec_state.recommendation
        state["recommendation_base"] = BASE_RECOMMENDATION
        state["recommendation_changed_by_hic"] = rec_state.recommendation != BASE_RECOMMENDATION
        uncertain_selected = [
            a for a in state.get("user_focus_areas", [])
            if a in {"Independent ownership", "Structured evaluation or screening experience"}
        ]
        state["hic_uncertain_areas_selected"] = uncertain_selected
        state["hic_triggered_hold"] = bool(
            condition.hic
            and rec_state.recommendation == "Hold for further review"
            and state["recommendation_changed_by_hic"]
            and uncertain_selected
        )
        _log(
            logger, state, "recommendation_presented",
            recommendation=rec_state.recommendation,
            agent_output=rendered.text,
            condition_id=condition.condition_id,
            explainability=condition.explainability,
            anthropomorphic_cues=condition.anthropomorphic_cues,
            hic=condition.hic,
            citation_chips=citation_ids,
            recommendation_base=state["recommendation_base"],
            recommendation_final=state["recommendation_final"],
            recommendation_changed_by_hic=state["recommendation_changed_by_hic"],
            hic_triggered_hold=state["hic_triggered_hold"],
            hic_uncertain_areas_selected=state["hic_uncertain_areas_selected"],
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
        if not state.get("hic_stage2_shown"):
            state["hic_stage2_shown"] = True
            state["hic_stage2_shown_at"] = _now_iso()
            _log(
                logger, state, "hic_stage2_shown",
                recommendation=rec_state.recommendation,
                screen=4,
                screen_name=_screen_name(4),
            )
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
            placeholder="Optional  -  add any specific focus or context here.",
        )

        col_examine, col_skip = st.columns([1, 1])
        with col_examine:
            examine_label = "Examine this" if condition.anthropomorphic_cues else "Examine"
            if st.button(examine_label, type="primary", key="submit_hic2_btn"):
                if not hic2_option and not hic2_free.strip():
                    st.info("Please select an area or enter a question before examining.")
                else:
                    try:
                        challenge_resp = agent.handle_stage2_challenge(
                            agent_state, hic2_option or "",
                            custom_question=hic2_free.strip(),
                        )
                    except Exception:
                        st.error("Could not retrieve a response  -  please try again.")
                    else:
                        state["_challenge_text"] = challenge_resp.response_text
                        state["hic2_option"] = hic2_option
                        state["hic_stage2_used"] = True
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
            if st.button("Continue to my decision", key="hic2_skip_btn"):
                state["stage2_done"] = True
                skip_latency = _seconds_between(state.get("hic_stage2_shown_at"))
                state["hic_stage2_skip_latency_seconds"] = skip_latency
                _log(
                    logger, state, "hic_stage2_skipped",
                    hic_stage2_shown=state.get("hic_stage2_shown", False),
                    hic_stage2_used=state.get("hic_stage2_used", False),
                    hic_stage2_skip_latency_seconds=skip_latency,
                )
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
            value=state.get("judgement_settledness") or 1,
            key="judgement_settledness_slider",
            label_visibility="collapsed",
        )
        if st.button("Confirm and continue to decision", type="primary", key="confirm_settledness"):
            state["judgement_settledness"] = int(settledness_val)
            state["judgement_settledness_at"] = _now_iso()
            state["recommendation_dwell_seconds"] = _seconds_between(state.get("recommendation_presented_at"), state.get("judgement_settledness_at"))
            if not state["judgement_settledness_logged"]:
                _log(
                    logger, state, "judgement_settledness_recorded",
                    judgement_settledness=int(settledness_val),
                    recommendation=rec_state.recommendation,
                    provenance_clicks=state.get("provenance_clicks", 0),
                    citation_evidence_inspected=bool(state.get("unique_citations_clicked", 0) > 0),
                    full_document_inspected=bool(state.get("role_full_viewed") or state.get("policy_full_viewed")),
                    recommendation_dwell_seconds=state.get("recommendation_dwell_seconds"),
                    hic_stage2_explored=bool(state.get("hic2_option")),
                )
                state["judgement_settledness_logged"] = True
            dwell = _finalize_screen_dwell(state, 4)
            _log(
                logger, state, "screen_completed",
                screen=4,
                screen_name=_screen_name(4),
                screen_dwell_seconds=dwell,
            )
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
    state["citation_click_count"] = int(state.get("citation_click_count", 0)) + 1
    state["citation_evidence_inspected"] = True
    state.setdefault("citations_clicked", []).append(chip.evidence_id)
    state["unique_citations_clicked"] = len(set(state.get("citations_clicked", [])))
    state["doc_view_opened_at"] = _now_iso()
    _log(
        logger, state, "citation_clicked",
        participant_id=state.get("participant_id", ""),
        condition_id=condition.condition_id,
        citation_id=chip.evidence_id,
        document_type=chip.document_key,
        section_number=chip.section_label,
        source_screen="recommendation",
        provenance_click_count=state["provenance_clicks"],
        citation_click_count=state["citation_click_count"],
        unique_citations_clicked=state["unique_citations_clicked"],
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
    """Render recommendation text with citation chips.

    Single-paragraph text (high-A conversational): rendered as one unbroken
    block with all chips shown as a compact row beneath  -  no mid-sentence
    interruptions.

    Multi-paragraph text (low-A report): chips appear below the paragraph
    that contains their section reference.
    """
    if not chips:
        st.write(text)
        return

    label_map = {s.section_label: s for s in chips}
    rendered_ids: set[str] = set()

    # Single conversational paragraph  -  render whole, chips at end
    if "\n\n" not in text.strip():
        styled = _style_section_refs(text.strip(), label_map)
        st.markdown(styled, unsafe_allow_html=True)
        max_cols = min(len(chips), 4)
        chip_cols = st.columns(max_cols)
        for i, chip in enumerate(chips):
            with chip_cols[i % max_cols]:
                _render_chip(chip, state, logger, condition)
        return

    # Multi-paragraph report  -  chips below the paragraph that cites them
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    for para in paragraphs:
        refs = list(dict.fromkeys(re.findall(r"Section\s+\d+\.\d+", para)))
        para_chips = [
            label_map[r]
            for r in refs
            if r in label_map and label_map[r].evidence_id not in rendered_ids
        ]

        styled = _style_section_refs(para, label_map)
        st.markdown(styled, unsafe_allow_html=True)

        if para_chips:
            max_cols = min(len(para_chips), 4)
            chip_cols = st.columns(max_cols)
            for i, chip in enumerate(para_chips):
                with chip_cols[i % max_cols]:
                    _render_chip(chip, state, logger, condition)
                rendered_ids.add(chip.evidence_id)

    # Overflow: chips not matched to any paragraph
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
        state["final_decision_at"] = _now_iso()
        state["time_from_recommendation_to_final_decision_seconds"] = _seconds_between(
            state.get("recommendation_presented_at"), state.get("final_decision_at")
        )
        state["time_from_judgement_settledness_to_final_decision_seconds"] = _seconds_between(
            state.get("judgement_settledness_at"), state.get("final_decision_at")
        )
        _log(
            logger, state, "final_decision_recorded",
            recommendation=ai_recommendation,
            final_human_decision=decision,
            recommendation_followed=decision == ai_recommendation,
            hold_reasons=hold_reasons,
            judgement_settledness=state.get("judgement_settledness"),
            time_from_recommendation_to_final_decision_seconds=state.get("time_from_recommendation_to_final_decision_seconds"),
            time_from_judgement_settledness_to_final_decision_seconds=state.get("time_from_judgement_settledness_to_final_decision_seconds"),
        )
        dwell = _finalize_screen_dwell(state, 7)
        _log(
            logger, state, "screen_completed",
            screen=7,
            screen_name=_screen_name(7),
            screen_dwell_seconds=dwell,
        )
        if not state.get("session_saved"):
            with st.spinner("Saving session data…"):
                saved = _save_session_to_github(state, condition, logger)
            state["session_saved"] = True
            if not saved:
                st.warning(
                    "Session data could not be saved to GitHub  -  please notify the researcher. "
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
        st.metric("Your decision", state.get("decision", " - "))
    with col2:
        st.metric("AI recommendation", state.get("ai_recommendation", " - "))
    st.caption(f"Session reference: {state.get('session_id', ' - ')}")
    st.divider()
    if st.session_state.get("has_return_url"):
        st.info("Click below to return to your survey and complete the questionnaire.")
        if st.button("Return to survey", type="primary", key="return_to_survey"):
            back_to_survey(done_flag=True)
    else:
        st.info("Please return to your survey tab and continue with the questionnaire.")


# ─── Entry point ──────────────────────────────────────────────────────────────

def run(condition_id: str) -> None:
    """Render one condition's UI over the shared case materials."""
    condition = get_condition(condition_id)

    st.set_page_config(
        page_title="AI Hiring Decision Assistant",
        page_icon=":briefcase:",
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

