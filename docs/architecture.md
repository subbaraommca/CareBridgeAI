# CareBridge AI Architecture

## System Position

CareBridge AI is a backend platform for transition-of-care workflows:

- ED summary
- medication reconciliation
- discharge and clinician handoff summary

The system is designed to be:

- FHIR R4-compliant at the interoperability boundary
- selective R5 feature support internally where it improves workflow modeling
- canonical-model driven
- ready for future A2A integration with Prompt Opinion

## Core Design

### R4 Baseline With Selective R5 Features

All downstream workflow logic operates on a normalized canonical patient snapshot. The platform remains aligned to an R4-compatible exchange baseline while allowing carefully bounded R5-oriented internal features where they simplify transition-of-care workflows.

### Version Compatibility Boundary

External systems are expected to be primarily R4 or R4B. The adapter layer reconciles version differences and supports selected R5-oriented internal features without breaking R4-facing interoperability.

### Canonical Model First

Agents and services should consume:

- `PatientSnapshot`
- workflow request/response contracts
- typed provenance and audit metadata

They should not depend directly on raw vendor FHIR payloads unless they are explicitly part of ingestion or persistence.

### A2A Readiness

Current orchestration is local and synchronous, but the system is already shaped around explicit workflow contracts, trace IDs, agent boundaries, and structured outputs. Those are the same seams needed for future agent-to-agent execution.

## Main Components

### FHIR Gateway

Responsibilities:

- call upstream FHIR servers
- fetch capability statement / metadata
- perform read and search operations
- preserve raw resource payloads

Key modules:

- `backend/app/services/fhir_gateway/client.py`
- `backend/app/services/fhir_gateway/metadata.py`
- `backend/app/services/fhir_gateway/bundle_parser.py`
- `backend/app/services/fhir_gateway/reference_resolver.py`

### Adapter Layer

Responsibilities:

- detect R4 or R4B inputs
- conservatively adapt external payloads toward internal canonical expectations
- preserve source data while minimizing destructive translation

Key module:

- `backend/app/services/adapters/r4_to_r5.py`

### Normalization

Responsibilities:

- convert raw FHIR resources into canonical domain models
- build `PatientSnapshot`
- isolate workflow logic from raw resource shape differences

Key modules:

- `backend/app/services/normalization/patient_mapper.py`
- `backend/app/services/normalization/encounter_mapper.py`
- `backend/app/services/normalization/medication_mapper.py`
- `backend/app/services/normalization/observation_mapper.py`

### Medication Safety

Responsibilities:

- deterministic duplicate medication checks
- similar-therapy checks
- allergy conflict checks
- missing dose/frequency checks
- verification question generation

Key modules:

- `backend/app/services/med_safety/duplicate_rules.py`
- `backend/app/services/med_safety/allergy_rules.py`
- `backend/app/services/med_safety/verification_rules.py`

### Summarization

Responsibilities:

- clinician-facing ED summary generation
- clinician-facing discharge/handoff summary generation
- patient-friendly discharge instructions
- prompt guardrails and fallback behavior

Key modules:

- `backend/app/services/summarization/gemini_client.py`
- `backend/app/services/summarization/prompt_manager.py`

### Orchestrator

Responsibilities:

- generate workflow trace IDs
- fetch patient context
- route execution by workflow mode
- combine outputs into a single workflow response
- aggregate provenance and artifacts

Key modules:

- `backend/app/agents/orchestrator_agent.py`
- `backend/app/agents/patient_context_agent.py`
- `backend/app/agents/ed_summary_agent.py`
- `backend/app/agents/medrec_agent.py`
- `backend/app/agents/transition_agent.py`

## Execution Flow

1. API receives a workflow request.
2. Orchestrator creates a trace ID.
3. Patient Context Agent retrieves raw FHIR resources through the FHIR Gateway.
4. If needed, the adapter layer reconciles source-version differences before normalization.
5. Normalization builds a canonical `PatientSnapshot`.
6. The orchestrator invokes one or more domain agents.
7. Outputs are merged into a typed workflow response with provenance, findings, and artifacts.
8. Audit and persistence scaffolding capture trace-level execution data.

## Current Boundaries

- synchronous request/response execution
- minimal PostgreSQL scaffolding without finalized schema migrations
- Gemini integration behind a wrapper with deterministic fallback
- no production authn/authz yet
- no external A2A transport yet

## Next Evolution

- durable workflow state and retries
- persistent storage of workflow runs, agent outputs, and raw FHIR resources
- async orchestration
- human review queues for medication and transition workflows
- Prompt Opinion A2A execution using the current workflow contracts as the exchange boundary
