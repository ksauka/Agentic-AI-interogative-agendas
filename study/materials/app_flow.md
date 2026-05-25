# Participant App Flow

## Constant Experience

All eight Streamlit apps use the same participant-facing sequence, materials,
and recommendation logic. The agent first compares CV evidence against internal company context and role requirements under the screening policy; only then are visible communication and control-cue overlays applied. Only the explainability, anthropomorphic-cue, and
Mixed-Initiative Control Cue overlays, operationalized as interrogative agendas, vary by assigned condition.

## Screens

1. Welcome and role framing

   Introduce the participant as the human decision-maker responsible for a
   screening recommendation.

2. Company context

   Display the identical company background relevant to the strategic role. It is part of the internal knowledge base used to interpret candidate fit and may be surfaced as provenance in explainability conditions.

3. Strategic role description

   Display the identical canonical **Role Description for Strategic Talent Operations Partner** with numbered required, preferred, transferable-evidence, and interpretation provisions. In explainability conditions, role provisions are available as provenance citations.

4. Recruiter screening policy

   Display the identical **AI-Assisted Strategic Hiring Screening Policy**,
   including its numbered rules for transferable evidence, uncertainty, and
   human decision authority. In explainability conditions, numbered policy
   provisions are available as provenance citations.

5. Candidate CV

   Ask the participant to upload a PDF/TXT/Markdown CV or paste CV text. The
   uploaded CV is embedded in a session-only vector collection. In the
   factorial study deployment, provide the same controlled borderline CV to
   every participant.

6. AI recommendation and decision support

   Retrieve from persisted company-context, role-description, and policy knowledge and the
   session CV comparison collection, then present the single assistant's recommendation
   with the assigned overlays.
   The recommendation must be one of: `Reject`, `Advance to human interview`,
   or `Hold for further review`.

7. Final human decision

   Ask the participant to select one of the same three actions, independently
   of whether it matches the assistant recommendation.

8. Post-task questionnaire

   Capture sense of agency, overreliance, manipulation checks, and relevant
   covariates.

At the decision stages, participants must still be able to inspect the role
description, screening policy, and candidate CV.
