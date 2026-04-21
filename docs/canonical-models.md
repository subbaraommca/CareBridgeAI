# Canonical Models

## Purpose

CareBridge AI uses canonical domain models to separate:

- external FHIR variation
- internal workflow logic
- downstream agent outputs

The canonical layer is patient-centric, grounded in an R4-compliant exchange model with selective R5-oriented internal features where useful.

## Raw FHIR Layer

### `RawFHIRResource`

Preserves the original upstream payload with stable metadata:

- `source_version`
- `resource_type`
- `resource_id`
- `fetched_at`
- `payload`

Use this layer for:

- gateway results
- persistence of source records
- replay/debugging
- adapter input

## Canonical Domain Layer

### `PatientDemographics`

Minimal patient identity and communication details:

- internal patient ID
- MRN
- name
- birth date
- gender
- phone / email
- preferred language

### `EncounterSummary`

Primary workflow encounter context:

- encounter ID
- class and status
- start / end timestamps
- facility and location
- attending clinician
- reason for visit
- discharge disposition

### `ConditionRecord`

Problem-oriented canonical condition view:

- condition ID
- code and display
- clinical and verification status
- category
- onset / abatement
- recorded time

### `AllergyRecord`

Allergy/intolerance safety view:

- allergy ID
- code
- substance
- reaction
- severity
- criticality
- clinical and verification status

### `MedicationRecord`

Medication reconciliation view:

- medication ID
- code and display
- status
- dosage text
- route
- frequency
- authored timestamp
- prescriber

### `ObservationRecord`

Observation summary view:

- observation ID
- code and display
- status
- value text or numeric value
- unit
- interpretation
- effective timestamp

### `ProvenanceRecord`

Workflow provenance attached to snapshots and responses:

- trace ID
- source system
- source version
- agent name
- recorded timestamp
- note
- optional confidence

### `PatientSnapshot`

The main canonical aggregate for workflow execution:

- one `PatientDemographics`
- optional primary `EncounterSummary`
- lists of conditions, allergies, medications, observations
- provenance
- assembly timestamp

This is the main boundary between ingestion and workflow logic.

## Model Usage Rules

- normalize once, reuse many times
- do not force agents to parse raw FHIR payloads
- preserve source provenance when moving into canonical form
- prefer additive evolution over breaking field churn

## Example Snapshot

```json
{
  "patient": {
    "patient_id": "cbai-patient-1001",
    "medical_record_number": "DEMO-MRN-1001",
    "given_name": "Taylor",
    "family_name": "Synthetic",
    "birth_date": "1978-09-12",
    "gender": "female",
    "preferred_language": "English"
  },
  "encounter": {
    "encounter_id": "cbai-encounter-ed-2001",
    "encounter_class": "EMER",
    "status": "finished",
    "facility_name": "CareBridge Demo Medical Center",
    "location_name": "Emergency Department Bay 4",
    "attending_clinician": "Avery Chen, MD",
    "reason_for_visit": "Dizziness and generalized weakness",
    "discharge_disposition": "Discharged home with close PCP follow-up"
  },
  "conditions": [
    {
      "condition_id": "cbai-condition-3001",
      "display": "Hypertension",
      "clinical_status": "active"
    }
  ],
  "allergies": [
    {
      "allergy_id": "cbai-allergy-4001",
      "substance": "Penicillin",
      "severity": "moderate"
    }
  ],
  "medications": [
    {
      "medication_id": "cbai-medreq-5001",
      "display": "Lisinopril 10 mg tablet",
      "status": "active",
      "dosage_text": "Take 1 tablet by mouth once daily"
    },
    {
      "medication_id": "cbai-medstmt-6001",
      "display": "Lisinopril 20 mg tablet",
      "status": "active"
    }
  ],
  "observations": [
    {
      "observation_id": "cbai-observation-7001",
      "display": "Potassium",
      "value_numeric": 5.8,
      "unit": "mmol/L",
      "interpretation": "High"
    }
  ]
}
```

## Provenance Extensions

The audit/provenance support layer also defines:

- source system provenance
- normalization provenance
- summarization provenance
- combined provenance envelope

Those structures support future durable workflow execution and A2A exchange without changing the canonical patient model itself.
