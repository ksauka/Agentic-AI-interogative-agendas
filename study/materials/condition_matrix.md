# Experimental Condition Matrix

## Design Rule

The agent uses one constant retrieval-grounded hiring recommendation policy. The experimental
conditions vary only three visible overlays in the locked replacement design
summarized in `../../docs/research_brief.md`:

- `E`: provenance-based explainability;
- `A`: anthropomorphic communication cues; and
- `C`: mixed-initiative control cues through interrogative agendas.

The fixed substantive calculation is `Recommendation = CV fit against (company context + role requirements + policy rules)`: the CV is the submitted evidence; company context, role description, and screening policy are the indexed knowledge documents against which fit is evaluated. This calculation occurs before any visible overlay is delivered.

Because each overlay is either OFF or ON, the specification implies eight
conditions. This matrix is an implementation derivative of the supplied
agent specification, not an additional theoretical claim.

## Eight Conditions

| App | ID | E | A | C | Required visible treatment |
| --- | --- | --- | --- | --- | --- |
| 1 | `E0_A0_C0` | Low | Low | No | Direct recommendation, neutral professional phrasing, no routine decision checkpoint. |
| 2 | `E0_A0_C1` | Low | Low | Yes | Neutral wording plus a question, option, checkpoint, or decision-right reminder. |
| 3 | `E1_A0_C0` | High | Low | No | Document-grounded rationale, neutral professional phrasing, direct recommendation. |
| 4 | `E1_A0_C1` | High | Low | Yes | Document-grounded rationale plus a neutral decision checkpoint. |
| 5 | `E0_A1_C0` | Low | High | No | Direct recommendation with mild cooperative or first-person phrasing. |
| 6 | `E0_A1_C1` | Low | High | Yes | Mild cooperative phrasing plus a decision checkpoint, with minimal rationale. |
| 7 | `E1_A1_C0` | High | High | No | Document-grounded rationale with mild cooperative phrasing and direct recommendation. |
| 8 | `E1_A1_C1` | High | High | Yes | Document-grounded rationale, mild cooperative phrasing, and a decision checkpoint. |

## Constant Base Behavior

In every condition, the assistant:

- retrieves from the same company context, strategic role description, and recruiter screening policy as internal knowledge, and compares the same borderline candidate CV against those documents;
- produces only `Reject`, `Advance to human interview`, or `Hold for further review`;
- keeps candidate evidence and recommendation logic identical across apps;
- remains bounded, polite, coherent, and professionally usable;
- does not invent CV evidence, role requirements, or hiring-policy facts; and
- does not disclose or describe the experimental manipulations.

## Overlay Delivery Rules

### Explainability (`E`)

When `E=1`, the recommendation should include concise visible reasons tied to
retrieved CV evidence, role requirements, and screening-policy rules. When
`E=0`, the recommendation should have little or no visible rationale beyond
what is needed for coherence.

### Anthropomorphic Communication (`A`)

When `A=1`, the wording may include mild first-person phrasing, cooperative
acknowledgements, and limited affiliative framing. When `A=0`, wording should
be neutral, professional, and socially thin without becoming impolite.

### Mixed-Initiative Control (`C`)

When `C=1`, before moving the participant toward a hiring decision the
assistant should offer a choice, ask a targeted question, insert a checkpoint,
or remind the user that the final decision is theirs. When `C=0`, it may
present its recommendation directly without a designed checkpoint.

## Contamination Checks

Pilot review should flag:

- rationale in an `E=0` turn beyond minimal conversational necessity;
- warmth-heavy, affiliative, or strongly first-person language in an `A=0`
  turn;
- omitted checkpoint before decision progression in a `C=1` turn;
- routine decision checkpoints in a `C=0` turn; and
- underlying recommendation or evidence differing between condition cells.
