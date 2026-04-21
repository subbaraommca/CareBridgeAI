# API Contracts

## Base Notes

- Transport: JSON over HTTP
- Current execution style: synchronous
- Traceability: every workflow response returns a `correlation_id` used as the workflow trace ID
- Internal model basis: canonical patient snapshot built from an R4-compliant baseline with selective R5 feature support

## Endpoints

### `GET /health`

Returns basic service liveness.

Example response:

```json
{
  "status": "ok",
  "service": "CareBridge AI",
  "timestamp": "2026-04-17T18:22:11.314218Z"
}
```

### `POST /api/workflow/run`

Runs the orchestrated workflow entrypoint.

Example request:

```json
{
  "mode": "full_transition_of_care",
  "patient_id": "cbai-patient-1001",
  "encounter_id": "cbai-encounter-ed-2001",
  "requested_by": "demo-user",
  "metadata": {
    "fhir_base_url": "https://example.org/fhir",
    "access_token": "demo-token"
  }
}
```

Example response:

```json
{
  "status": "completed",
  "mode": "full_transition_of_care",
  "patient_id": "cbai-patient-1001",
  "encounter_id": "cbai-encounter-ed-2001",
  "correlation_id": "3b52d4da-5f02-4709-b3d7-89f38ef7bb66",
  "message": "full_transition_of_care workflow completed successfully.",
  "summary_text": "ED Summary\n...\n\nMedication Reconciliation\n...\n\nTransition Summary\n...",
  "findings": [
    {
      "finding_id": "fd0f7ae0-d8d2-4697-9c97-79fc38c9c8a0",
      "category": "possible_duplicate_therapy",
      "severity": "low",
      "medication_id": "cbai-medstmt-6001",
      "medication_display": "Lisinopril 20 mg tablet",
      "rationale": "Medication names are highly similar and may require review.",
      "recommended_action": "Verify whether both entries should remain active."
    }
  ],
  "artifacts": {
    "trace_id": "3b52d4da-5f02-4709-b3d7-89f38ef7bb66",
    "requested_mode": "full_transition_of_care",
    "source_version": "R4",
    "raw_resource_count": 7,
    "ed_summary": {
      "summary_text": "..."
    },
    "medrec": {
      "summary_text": "...",
      "verification_questions": [
        "Should the active lisinopril dose be 10 mg or 20 mg daily?"
      ]
    },
    "transition": {
      "summary_text": "...",
      "patient_instructions": "..."
    }
  }
}
```

### `POST /api/context/fetch`

Fetches and normalizes patient context only.

Example request:

```json
{
  "patient_id": "cbai-patient-1001",
  "encounter_id": "cbai-encounter-ed-2001"
}
```

Example response:

```json
{
  "status": "completed",
  "patient_id": "cbai-patient-1001",
  "encounter_id": "cbai-encounter-ed-2001",
  "source_version": "R4",
  "raw_resource_count": 7,
  "message": "Patient context fetched and normalized successfully.",
  "patient_snapshot": {
    "patient": {
      "patient_id": "cbai-patient-1001",
      "given_name": "Taylor",
      "family_name": "Synthetic"
    },
    "medications": [
      {
        "medication_id": "cbai-medreq-5001",
        "display": "Lisinopril 10 mg tablet",
        "status": "active"
      }
    ]
  }
}
```

### `POST /api/medrec/run`

Runs deterministic medication reconciliation.

Example request:

```json
{
  "patient_id": "cbai-patient-1001",
  "encounter_id": "cbai-encounter-ed-2001",
  "patient_snapshot": {
    "patient": {
      "patient_id": "cbai-patient-1001",
      "given_name": "Taylor",
      "family_name": "Synthetic"
    },
    "allergies": [
      {
        "allergy_id": "cbai-allergy-4001",
        "substance": "Penicillin"
      }
    ],
    "medications": [
      {
        "medication_id": "cbai-medreq-5001",
        "display": "Lisinopril 10 mg tablet",
        "status": "active"
      },
      {
        "medication_id": "cbai-medstmt-6001",
        "display": "Lisinopril 20 mg tablet",
        "status": "active"
      }
    ]
  }
}
```

Example response:

```json
{
  "status": "accepted",
  "mode": "med_rec",
  "patient_id": "cbai-patient-1001",
  "encounter_id": "cbai-encounter-ed-2001",
  "correlation_id": "7c18ce3d-8c76-4360-987a-e0b258bb9488",
  "message": "Medication reconciliation completed deterministically.",
  "summary_text": "Reviewed 2 medications and found 1 issues. 1 verification questions were generated.",
  "issues": [
    {
      "category": "possible_duplicate_therapy",
      "severity": "low",
      "medication_display": "Lisinopril 20 mg tablet"
    }
  ],
  "verificationQuestions": [
    "Should the active lisinopril dose be 10 mg or 20 mg daily?"
  ]
}
```

### `POST /api/transition/run`

Runs transition summary generation directly.

Example request:

```json
{
  "mode": "discharge_handoff",
  "patient_id": "cbai-patient-1001",
  "encounter_id": "cbai-encounter-ed-2001",
  "transition_type": "discharge"
}
```

Example response:

```json
{
  "status": "accepted",
  "mode": "discharge_handoff",
  "patient_id": "cbai-patient-1001",
  "encounter_id": "cbai-encounter-ed-2001",
  "correlation_id": "50db078a-5d16-4f95-a249-f6ef9d87b418",
  "message": "Transition summary generated.",
  "summary_text": "Transition Summary\n...",
  "handoff_sections": {
    "clinician_summary": "Transition Summary\n...",
    "patient_instructions": "What Happened Today\n..."
  }
}
```

## Error Shape

Current route-level failures return:

```json
{
  "detail": "Unable to process workflow request."
}
```

## Contract Direction

- Preserve stable request/response envelopes
- keep canonical patient data reusable across endpoints
- use `correlation_id` as the primary trace handle
- keep workflow-specific artifacts additive rather than fragmenting the base contract
