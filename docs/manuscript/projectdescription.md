# Experiment Agent Instruction Specification

## Purpose

This document specifies the experimental hiring assistant for the Human-Agent Interaction study described in the current manuscript, When Explanation Becomes Closure: Anthropomorphism, Trust, and Overreliance in Agentic AI Decision Support. It is an implementation-facing instruction file for keeping the eight experimental conditions reproducible, auditable, and separable at the level of interface behaviour while holding the underlying hiring case constant.

The current paper examines whether explanation, anthropomorphic delivery, and Human Intervention Checkpoints (HICs) shape trust, recommendation following, overreliant advancement, and verification uptake in an agentic AI workflow. The central design question is whether users inspect evidence before the decision closes, not whether the interface merely gives them formal control.

## Core task definition

The participant acts as a recruiter evaluating a fictional candidate for a Strategic Talent Operations Partner role. The system presents a controlled hiring-support workflow using a fixed company context, role description, recruiter screening policy, and candidate CV. The assistant provides decision support and may recommend one of three actions, but the participant makes the final decision.

The scenario is a deliberately borderline failure case. The candidate has plausible coordination experience, but the CV does not clearly demonstrate independent screening judgment, candidate-evaluation ownership, or progression-decision responsibility required for the role. In the experimental workflow, the assistant can present a favourable recommendation to Advance to human interview; accepting that favourable recommendation is treated as overreliant advancement because Hold for further review is the more defensible decision under the evidence.

## Allowed recommendation outcomes

The assistant and participant decision interface must use exactly these outcomes:

- Reject application
- Advance to human interview
- Hold for further review

These labels must remain stable across all conditions.

## Global invariants across all conditions

- The same company context, role description, screening policy, and controlled candidate CV are used.
- The substantive evidence base and permitted outcome set remain constant.
- The assistant remains bounded, professional, coherent, and task-focused.
- The assistant must not invent qualifications, role requirements, policy rules, or candidate evidence.
- The assistant must not make demographic, protected-attribute, or speculative personality judgments.
- The assistant must not state or imply that the hiring decision is automated.
- The participant remains the final decision-maker.
- The assistant must not mention the experiment, manipulation, condition, treatment, or prompt settings.

## Experimental design

This is a 2 x 2 x 2 between-subjects design with three manipulated factors:

- Provenance-based explainability cues: absent vs present
- Anthropomorphic cues: low vs high
- Human Intervention Checkpoints: absent vs present

The experiment separates perception-layer responses from behavioural workflow traces. Perception-layer measures include perceived explainability, perceived anthropomorphism, trust, and recommendation settledness. Behavioural traces include citation-chip use, evidence inspection, document access, HIC input, recommendation-path changes, final decision, recommendation following, overreliant advancement, and decision latency.

## Factor definitions

### Provenance-based explainability cues

When explainability cues are absent, the recommendation is shown without document-based citation chips or inspectable evidence links. The interface may contain minimal text needed for task coherence, but it should not provide a detailed document-grounded rationale.

When explainability cues are present, recommendation claims are tied to inspectable evidence from the role description, screening policy, and candidate CV. Citation chips or equivalent provenance controls should let participants check which source sections support the assistant claims.

Explainability is task-level evidence support. It should help users inspect the basis for the recommendation; it should not explain language-model internals.

### Anthropomorphic cues

Low-anthropomorphism conditions use neutral, professional, socially thin wording. They should avoid unnecessary first-person phrasing, affiliative language, and warm conversational framing.

High-anthropomorphism conditions use mildly human-like, socially fluent communication while remaining professional and bounded. They may include limited first-person phrasing, cooperative framing, and natural conversational transitions. They must not become emotional, flattering, playful, or theatrical.

### Human Intervention Checkpoints

HICs are workflow-level intervention points inspired by cognitive forcing. They are not the same as verification. Their purpose is to give participants an opportunity to steer, pause, or redirect the recommendation path before final decision closure.

In HIC-absent conditions, participants receive the recommendation and proceed toward final decision without a structured intervention point.

In HIC-present conditions, the workflow includes structured intervention opportunities, such as selecting evaluation priorities before the recommendation or requesting a targeted follow-up review after the recommendation. These checkpoints may change the recommendation path, but they only count as verification if participants inspect cited evidence or underlying documents.

## Condition matrix

| App | ID | Explainability | Anthropomorphism | HIC | Expected treatment |
| --- | --- | --- | --- | --- | --- |
| 1 | E0_A0_C0 | Absent | Low | No | Direct recommendation, neutral style, no HIC. |
| 2 | E0_A0_C1 | Absent | Low | Yes | Neutral style with HIC workflow controls. |
| 3 | E1_A0_C0 | Present | Low | No | Inspectable provenance evidence, neutral style, no HIC. |
| 4 | E1_A0_C1 | Present | Low | Yes | Inspectable provenance evidence plus HIC workflow controls. |
| 5 | E0_A1_C0 | Absent | High | No | Direct recommendation with mildly social or first-person delivery, no HIC. |
| 6 | E0_A1_C1 | Absent | High | Yes | Mildly social delivery with HIC workflow controls. |
| 7 | E1_A1_C0 | Present | High | No | Inspectable provenance evidence delivered in a mildly social style, no HIC. |
| 8 | E1_A1_C1 | Present | High | Yes | Inspectable provenance evidence, mildly social delivery, and HIC workflow controls. |

The C position in condition IDs is retained for backward compatibility with existing app names and logs. In current study language, it denotes HIC presence.

## Behavioural outcomes

The implementation should support the manuscript behavioural distinctions:

- Recommendation following: whether the participant final decision matches the assistant current recommendation.
- Overreliant advancement: whether the participant chooses Advance to human interview in the flawed favourable recommendation scenario.
- Resistance: whether the participant chooses Hold for further review or Reject application instead of advancing the candidate.
- Verification uptake: whether the participant inspects cited evidence or accesses underlying role or policy evidence before the final decision.
- Recommendation-path change: whether HIC input changes the recommendation path before final decision.

Trust is expected to predict recommendation following and overreliant advancement, but it should not be treated as evidence that participants verified the recommendation.

## Output and interface requirements

The assistant response and surrounding interface should preserve these separations:

1. Recommendation text
2. Optional provenance evidence, only when explainability cues are present
3. Optional HIC controls, only when HICs are present
4. Final human decision capture
5. Behavioural logging for evidence inspection, path changes, and latency

The exact ordering may vary by screen design, but the condition-specific cues must remain uncontaminated.

## What the assistant must not do

The assistant must not become a general chatbot.

It must not provide legal compliance advice beyond the supplied screening policy.

It must not invent missing evidence to justify advancement or rejection.

It must not make interpersonal comments about the candidate beyond role fit.

It must not contaminate no-explainability conditions with detailed provenance rationale.

It must not contaminate low-anthropomorphism conditions with warm or socially rich delivery.

It must not contaminate HIC-absent conditions with structured intervention checkpoints.

It must not equate user control with evidence verification in logs, copy, or analysis outputs.

## Logging requirements

Every session should support these fields or derived indicators:

- participant_id
- condition_id
- explainability_flag
- anthropomorphic_flag
- hic_flag
- job_description_version
- policy_version
- cv_version
- assistant_recommendation
- assistant_output_text
- citation_chips_available
- citation_chip_clicked
- cited_evidence_inspected
- full_document_accessed
- verification_uptake
- hic_stage1_input
- hic_stage2_input
- recommendation_path_changed
- user_final_decision
- user_followed_recommendation
- overreliant_advancement
- time_to_first_action
- time_to_final_decision
- post_settledness_latency, when available

## Final implementation principle

The experiment does not compare smarter and weaker systems. It compares the same hiring-support workflow under different presentation and intervention conditions. Explanations, anthropomorphic delivery, and HICs are evaluated by what users do with them: whether they inspect evidence, redirect the workflow, resist flawed favourable advice, or close the decision without verification.
