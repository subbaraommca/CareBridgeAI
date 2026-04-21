# Workflow Specifications

## Workflow Modes

CareBridge AI currently supports four workflow modes:

- `ed_summary`
- `med_rec`
- `discharge_handoff`
- `full_transition_of_care`

## Mode Behavior

### `ed_summary`

Purpose:

- generate a clinician-facing ED summary from canonical patient context

Execution path:

1. fetch patient context
2. adapt R4 input if required
3. normalize into `PatientSnapshot`
4. run ED Summary Agent

Primary output:

- `summary_text`

### `med_rec`

Purpose:

- run deterministic medication reconciliation without LLM dependence

Execution path:

1. fetch patient context
2. normalize medications and allergies
3. run duplicate, therapy, allergy, and completeness checks
4. generate verification questions

Primary outputs:

- `issues`
- `verificationQuestions`
- `summary_text`

### `discharge_handoff`

Purpose:

- produce transition-of-care content for discharge or clinician handoff
- include medication reconciliation findings alongside the transition summary

Execution path:

1. fetch patient context
2. normalize to `PatientSnapshot`
3. run medication reconciliation
4. run Transition Agent
5. combine both outputs

Primary outputs:

- transition `summary_text`
- handoff sections
- medication findings

### `full_transition_of_care`

Purpose:

- produce the full transition bundle for downstream clinician review or future A2A exchange

Execution path:

1. fetch patient context
2. adapt and normalize
3. run ED Summary Agent
4. run MedRec Agent
5. run Transition Agent
6. merge outputs into one workflow response

Primary outputs:

- ED summary
- medication findings and verification questions
- discharge/handoff summary
- aggregated provenance and artifacts

## Shared Workflow Contract

Common request fields:

- `mode`
- `patient_id`
- `encounter_id`
- optional `patient_snapshot`
- optional `source_resources`
- `requested_by`
- `correlation_id`
- `metadata`

Common response fields:

- `status`
- `mode`
- `patient_id`
- `encounter_id`
- `correlation_id`
- `message`
- `summary_text`
- `findings`
- `patient_snapshot`
- `provenance`
- `artifacts`

## Example Mode Matrix

| Mode | Context Fetch | ED Summary | Med Rec | Transition Summary |
| --- | --- | --- | --- | --- |
| `ed_summary` | Yes | Yes | No | No |
| `med_rec` | Yes | No | Yes | No |
| `discharge_handoff` | Yes | No | Yes | Yes |
| `full_transition_of_care` | Yes | Yes | Yes | Yes |

## Product Constraints

- summarize only supplied data
- keep medication safety checks deterministic
- preserve traceability through provenance and audit records
- keep raw source resources available for replay and review
- avoid embedding vendor-specific FHIR logic inside workflow agents

## A2A Direction

These workflows are intentionally defined as explicit contracts rather than implicit function calls. That keeps them ready for future agent-to-agent execution where:

- patient context can be provided by one agent
- medication review can be delegated independently
- transition summarization can be called as a separate capability
- the orchestrator can remain the trace and policy boundary
