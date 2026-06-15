# Interaction Logging Schema

## Purpose

This schema operationalizes the audit and behavioral logging requirements for
the locked hiring-decision design recorded in
`../materials/condition_matrix.md`. It is intended for refinement
when the interaction platform and survey implementation are chosen.

Each record represents one agent turn and the participant response to that
turn, where available.

## Turn-Level Fields

| Field | Type | Description |
| --- | --- | --- |
| `session_id` | string | Pseudonymous interaction session identifier. |
| `participant_id` | string | Pseudonymous participant identifier; do not store direct identifiers here. |
| `turn_id` | integer | Sequential agent turn number within the session. |
| `timestamp_utc` | datetime | Time at which the agent turn was emitted. |
| `condition_id` | enum | One of `E0_A0_C0` through `E1_A1_C1`. |
| `explainability_on` | boolean | Assigned provenance-based explainability overlay. |
| `anthropomorphic_cues_on` | boolean | Assigned anthropomorphic communication overlay. |
| `hic_on` | boolean | Assigned Human Intervention Checkpoint condition. The legacy `control_cues_on` field may be retained as an alias for compatibility. |
| `candidate_cv_received` | event | Records uploaded/pasted candidate source type and character count; CV text is not duplicated in the event log. |
| `retrieval_backend` | string | Retrieval implementation used for the recommendation turn, for example `chroma_persisted_internal_plus_uploaded_cv:text-embedding-3-small`. |
| `generation_backend` | string | Generation implementation used for the recommendation turn, for example `openai_responses:gpt-4o-mini-2024-07-18`. |
| `company_citation` | string | Company-context provenance label surfaced with the rationale when explanation is displayed; blank when unavailable or hidden. |
| `role_citation` | string | Numbered role-description provision surfaced as provenance when explanation is displayed, for example `Section 5.4`; blank when unavailable or hidden. |
| `policy_citation` | string | Numbered screening-policy provision surfaced as provenance when explanation is displayed, for example `Section 6.4`; blank when unavailable or hidden. |
| `knowledge_sources` | array[string] | Fixed internal knowledge sources: `company_context`, `role_description`, and `screening_policy`. |
| `comparison_input` | string | Fixed submitted evidence being assessed against knowledge documents: `candidate_cv`. |
| `user_input` | text | Participant message preceding the agent output. |
| `agent_output` | text | Output displayed to the participant. |
| `recommendation` | enum | `reject`, `advance_to_human_interview`, `hold_for_further_review`, or blank before recommendation delivery. |
| `final_human_decision` | enum | The same three hiring actions, once selected by the participant. |
| `recommendation_followed` | boolean | Whether the final human decision matches the assistant recommendation. |
| `action_types` | array[enum] | Any of `materials_displayed`, `evidence_requested`, `recommendation_presented`, `question_asked`, `options_presented`, `decision_recorded`, or `other`. |
| `rationale_present` | boolean | Whether a task-facing reason for a proposed action appears. |
| `first_person_present` | boolean | Whether mild first-person agent phrasing appears. |
| `cooperative_cue_present` | boolean | Whether cooperative/affiliative framing appears. |
| `checkpoint_present` | boolean | Whether a confirmation or pause before advancement appears. |
| `options_present` | boolean | Whether the agent provides user-selectable alternatives. |
| `divergence_signal_present` | boolean | Whether the agent explicitly signals differing possible directions or a mismatch to resolve. |
| `decision_right_reminder_present` | boolean | Whether the participant is explicitly reminded of final choice/control. |
| `substantive_advancement` | boolean | Whether the output provides a recommendation or progresses the hiring decision. |
| `user_response_type` | enum | `inspected_evidence`, `asked_clarification`, `selected_decision`, `no_response`, or `unclear`. |
| `verification_uptake` | boolean | Whether the participant inspects cited evidence or accesses underlying role/policy evidence before the final decision. |
| `notes` | text | Coder or system notes for exceptional cases. |

## Derived Behavioral Indicators

| Indicator | Proposed computation |
| --- | --- |
| Recommendation acceptance | Whether, or the proportion of cases where, `recommendation_followed=true`. |
| Verification uptake | Whether the participant inspects cited evidence or accesses underlying role/policy evidence before selecting the final action. |
| Citation and document inspection | Count or rate of citation-chip clicks, cited-section views, and full-document access events. |
| Override frequency | Count or proportion of final decisions that differ from the recommendation. |

## Manipulation Delivery Checks

For initial pilots, delivery can be audited with these expectations:

| Assigned overlay | Expected logged evidence |
| --- | --- |
| `explainability_on=true` | `rationale_present=true` for a delivered recommendation. |
| `explainability_on=false` | `rationale_present=false` except documented coherence exceptions. |
| `anthropomorphic_cues_on=true` | At least one relevant social cue may be present; excessive warmth remains a violation. |
| `anthropomorphic_cues_on=false` | `first_person_present=false` and `cooperative_cue_present=false` except minimal politeness. |
| `hic_on=true` | At least one HIC interaction opportunity is available before final-decision closure, such as evaluation-priority selection or targeted follow-up review. |
| `hic_on=false` | Routine HIC workflow controls should not appear. |

## Open Implementation Decisions

- Whether field coding is generated automatically, coded manually during
  pilots, or verified through both methods.
- How the interface records evidence inspection depth, recommendation-path changes, and post-settledness latency.
- Storage, consent, access control, and retention procedures for interaction
  text and participant metadata.
