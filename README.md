# Agentic AI interogative agendas

A dedicated research workspace for the Human-AI interaction project on
preserving human agency during agentic retrieval-grounded hiring decision
support.

The manuscript uses the construct name **Mixed-Initiative Control Cues**, operationalized as interrogative agendas: questions,
options, checkpoints, divergence signals, and explicit decision-right
reminders that make agent initiative contestable before a task advances. The
repository name retains the requested spelling, `interogative`.

## Research Focus

The project examines whether:

- provenance-based explainability and anthropomorphic communication cues
  increase overreliance on AI advice;
- overreliance reduces a user's sense of agency; and
- Mixed-Initiative Control Cues protect agency by weakening that negative
  relationship.

The confirmed application context is screening a borderline candidate for a
strategic role. A single assistant retrieves from the role description,
recruiter policy, and CV, recommends a hiring action, and leaves the final
decision with the participant.

The substantive decision pipeline is fixed across conditions: the CV is the submitted evidence compared against three internal knowledge documents - company context, role description, and screening policy. The role description specifies requirements; the policy controls interpretation and permitted outcomes; and the company context supplies the organisational setting for fit. In compact form: `Recommendation = CV fit against (company context + role requirements + policy rules)`. Communication overlays are applied only after the recommendation is generated.

## Current Contents

```text
docs/
  manuscript/HAI_draft.tex  Original ACM-format draft copied from anthrokit.
  manuscript/projectdescription.md  Agent implementation specification.
  research_brief.md          Extracted model, hypotheses, and study needs.
  incoming/                  New notes, sources, and material to incorporate.
study/
  materials/                 Condition matrix, hiring materials, procedures.
  measures/                  Logging schema, scales, instruments, codebooks.
  analysis/                  Analysis plans and scripts.
apps/                        Eight Streamlit condition entry points.
src/agentic_hiring/          Shared retrieval, rendering, logging, and UI code.
tests/                       Experimental-invariance and retrieval tests.
  data/                      Local research data; contents ignored by Git.
outputs/                     Generated results and reports; ignored by Git.
```

## Source Manuscript

The starting manuscript was copied from
`../anthrokit/Docs/HAI draft.md`. Although the original filename ends in
`.md`, its content is LaTeX and is stored here as
`docs/manuscript/HAI_draft.tex`.

That copied manuscript and the supplied `projectdescription.md` currently
refer to the earlier pitch-refinement version of the study. They are retained
as source files until the manuscript-facing replacements are supplied. The
draft also references `hai_acm_references_v2.bib`, which was not present.

## Locked Study Design

The replacement design is one retrieval-grounded hiring assistant, externally
experienced as one coherent agent, with three binary communication overlays:
provenance-based explainability, anthropomorphic communication cues, and
Mixed-Initiative Control Cues. The eight-condition between-subjects design is recorded in
`study/materials/condition_matrix.md`, with required delivery and user-response
events in `study/measures/logging_schema.md`.

## Adding Material

Put new conceptual notes, citations, design decisions, or source documents in
`docs/incoming/`. Study instruments and implementation materials can be
developed under `study/` as the research design is refined.

## Agentic RAG Implementation

The runnable system is a single agent, not a multi-agent orchestration. Its
internal pipeline is implemented in `src/agentic_hiring/rag_agent.py`:

1. LangChain creates internal knowledge objects from the company context, the canonical `study/materials/knowledge_base/strategic_talent_operations_partner_role_description.md` role description, and the canonical `study/materials/knowledge_base/ai_assisted_strategic_hiring_screening_policy.md` policy document, then splits the internal materials into retrievable provenance sections.
2. Chroma persists those internal document embeddings in
   `study/vector_store/company_knowledge/` and reopens the same content-versioned
   collection on later sessions. When a participant supplies a PDF or text CV,
   it is embedded in a separate session-only collection and is not written into
   the internal company collection.
3. Retrieval draws jointly from the internal company collection and the
   uploaded CV using OpenAI `text-embedding-3-small` embeddings.
4. The OpenAI Responses API uses the pinned model snapshot
   `gpt-4o-mini-2024-07-18` with Structured Outputs to produce the grounded
   basis for the recommendation.
5. The application applies the assigned explainability, anthropomorphic-cue,
   and Mixed-Initiative Control Cue overlay in the participant-facing response.
6. In high-explainability conditions, the recommendation displays separately validated role-description and policy provenance citations, such as role `Section 5.4` and policy `Section 6.4`.
7. The logger records the retrieval and generation backend used for the
   recommendation turn.

The live agent selects among `Reject`, `Advance to human interview`, and
`Hold for further review` based only on retrieved internal materials and the
uploaded CV. For the 2 x 2 x 2 experiment, supply the same controlled CV to
every participant so candidate variation does not confound the communication
manipulations. This prototype uses only fictional candidate material and must
not be used for real employment decisions.

If no `OPENAI_API_KEY` is configured, the app runs an explicitly labelled
lexical/protocol fallback for local development. Set
`AGENTIC_REQUIRE_LIVE_RAG=true` during study deployment so the app refuses to
continue if live RAG is unavailable.

## Setup

```bash
cd "/home/kudzai/projects/Agentic AI interogative agendas"
/home/kudzai/miniconda3/envs/esd_platform/bin/python -m pip install -r requirements.txt
export OPENAI_API_KEY="your-api-key"
export AGENTIC_REQUIRE_LIVE_RAG=true

# Before opening the app to participants, persist the internal policy/role index:
PYTHONPATH=src /home/kudzai/miniconda3/envs/esd_platform/bin/python scripts/build_internal_knowledge_base.py
```

The pre-index command embeds the company context, canonical role description, and recruiter
policy as internal knowledge. Candidate CVs are embedded after upload in session-only comparison collections.

For local execution, the app reads only `OPENAI_API_KEY` and
`AGENTIC_REQUIRE_LIVE_RAG` from `.env`; it does not load unrelated secrets.
Store `OPENAI_API_KEY` as a deployment secret for a shared Streamlit app; do
not commit it to this repository. A non-secret template is in `.env.example`.

Launch one assigned condition, for example:

```bash
/home/kudzai/miniconda3/envs/esd_platform/bin/python -m streamlit run apps/app_01_lowE_lowA_noIA.py
```

| App | Entry point | Condition |
| --- | --- | --- |
| 1 | `apps/app_01_lowE_lowA_noIA.py` | Low E, Low A, No IA |
| 2 | `apps/app_02_lowE_lowA_IA.py` | Low E, Low A, Yes IA |
| 3 | `apps/app_03_highE_lowA_noIA.py` | High E, Low A, No IA |
| 4 | `apps/app_04_highE_lowA_IA.py` | High E, Low A, Yes IA |
| 5 | `apps/app_05_lowE_highA_noIA.py` | Low E, High A, No IA |
| 6 | `apps/app_06_lowE_highA_IA.py` | Low E, High A, Yes IA |
| 7 | `apps/app_07_highE_highA_noIA.py` | High E, High A, No IA |
| 8 | `apps/app_08_highE_highA_IA.py` | High E, High A, Yes IA |

Run automated validation with:

```bash
PYTHONPATH=src /home/kudzai/miniconda3/envs/esd_platform/bin/python -m unittest discover -s tests -v
```

## OpenAI References

The implementation follows official OpenAI documentation for the Responses
API and Structured Outputs, which supports Python SDK parsing into a Pydantic
schema, and the official model documentation for `gpt-4o-mini` and
`text-embedding-3-small`:

- https://platform.openai.com/docs/api-reference/responses
- https://platform.openai.com/docs/guides/structured-outputs
- https://developers.openai.com/api/docs/models/gpt-4o-mini
- https://developers.openai.com/api/docs/models/text-embedding-3-small
