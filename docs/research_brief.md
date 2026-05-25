# Research Brief

## Working Topic

Preserving human agency in retrieval-grounded agentic hiring decision support
through Mixed-Initiative Control Cues.

## Core Problem

An agentic assistant can retrieve hiring criteria, analyse a borderline CV,
and make a recommendation, but the same initiative may reduce a participant's
experience of control and decision ownership. Explainability and
anthropomorphic communication may make an AI recommendation especially easy
to accept without sufficient scrutiny.

## Conceptual Model

Inputs:

- Provenance-based explainability
- Anthropomorphic communication cues

Mechanism:

- Overreliance on AI advice

Primary outcome:

- Sense of agency

Control-preserving moderator:

- Mixed-Initiative Control Cues (operationalized through interrogative agendas)

Candidate covariates to reconcile in the replacement manuscript:

- Trust propensity
- Prior LLM familiarity
- Recruitment or hiring-decision experience

## Hypotheses From The Draft

1. Provenance-based explainability increases overreliance on AI advice.
2. Anthropomorphic communication cues increase overreliance on AI advice.
3. Their combination produces greater overreliance than either cue alone.
4. Overreliance is negatively associated with sense of agency.
5. Mixed-Initiative Control Cues, operationalized as interrogative agendas, weaken the negative relationship between
   overreliance and sense of agency.

## Proposed Study Elements

The confirmed task context is recruiter screening for a strategic role. Each
participant can inspect the same company context, role description, screening
policy, and borderline candidate CV. A single retrieval-grounded assistant
uses these materials to issue one of three recommendations:

- Reject
- Advance to human interview
- Hold for further review

Its fixed substantive rule is: `Recommendation = CV fit against (company context + role requirements + policy rules)`. The CV is the submitted comparison input. Company context, the role description, and the screening policy form the internal knowledge base used to judge fit and to ground visible provenance explanations. These inputs and the recommendation process remain constant before any visible experimental overlay is applied.

The experiment manipulates explainability, anthropomorphic communication
cues, and Mixed-Initiative Control Cues during that recommendation interaction.

Mixed-Initiative Control Cues are operationalized through interrogative agendas consisting of:

- questions and user-selectable options;
- checkpoints before moving toward a hiring decision;
- divergence signalling; and
- explicit reminders that the final decision remains with the participant.

The primary self-report measures are six-item, seven-point Likert scales for
sense of agency and overreliance. The proposed behavioral indicators of
overreliance should capture acceptance of the AI recommendation, evidence
inspection and verification behavior, requests for clarification, and whether
the participant overrides or changes the recommended hiring action.

## Locked Implementation Model

The confirmed system is one coherent hiring assistant with an internal
retrieval-grounded decision pipeline: document reading, criteria retrieval,
recommendation generation, explanation generation, and user-facing decision
support. It is not a multi-agent experiment.

All eight apps use identical company, role, screening-policy, candidate, and
recommendation logic. Only these overlays vary:

- explainability OFF/ON: direct proposals versus concise task-facing reasons;
- anthropomorphic cues OFF/ON: socially thin professional wording versus mild
  first-person and cooperative wording; and
- mixed-initiative control OFF/ON: direct advancement versus interrogative
  agenda prompts before a participant decision.

This is a `2 x 2 x 2` between-subjects design with eight Streamlit app entry
points over one shared engine. The agent must not invent CV evidence or hiring
facts, expose the manipulation, or become more capable in one condition.

Study-ready derivatives:

- `study/materials/condition_matrix.md` identifies the eight conditions and
  treatment-delivery rules.
- `study/measures/logging_schema.md` turns the specified audit fields and
  behavioral indicators into a proposed turn-level event schema.

## Materials Still Needed

- Replacement manuscript and implementation specification for the hiring task
- Bibliography file for the replacement manuscript
- Final base prompt and overlay prompt text for the eight conditions
- Company context, strategic role description, recruiter screening policy,
  and controlled borderline CV
- Survey/instrument implementation and consent materials
- Implementation of interaction logging and manipulation checks
- Sampling, power, randomization, and statistical analysis decisions
- Data and results when the study is run
