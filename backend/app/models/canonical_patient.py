from datetime import UTC, date, datetime

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(UTC)


class CanonicalModel(BaseModel):
    """Base model for stable canonical CareBridge domain contracts."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class PatientDemographics(CanonicalModel):
    patient_id: str = Field(description="Primary internal patient identifier.")
    medical_record_number: str | None = Field(
        default=None,
        description="Primary MRN or equivalent enterprise patient identifier.",
    )
    given_name: str = Field(default="Unknown", description="Patient given or first name.")
    family_name: str = Field(default="Patient", description="Patient family or last name.")
    middle_name: str | None = Field(default=None, description="Patient middle name when available.")
    birth_date: date | None = Field(default=None, description="Patient date of birth.")
    gender: str | None = Field(default=None, description="Administrative gender value.")
    phone: str | None = Field(default=None, description="Preferred phone contact.")
    email: str | None = Field(default=None, description="Preferred email contact.")
    preferred_language: str | None = Field(
        default=None,
        description="Preferred language for communication.",
    )


class EncounterSummary(CanonicalModel):
    encounter_id: str = Field(description="Encounter identifier in the canonical domain.")
    encounter_class: str = Field(default="unknown", description="Encounter class or setting.")
    status: str = Field(default="unknown", description="Current lifecycle status for the encounter.")
    start_time: datetime | None = Field(default=None, description="Encounter start timestamp.")
    end_time: datetime | None = Field(default=None, description="Encounter end timestamp.")
    facility_name: str | None = Field(default=None, description="Facility responsible for the encounter.")
    location_name: str | None = Field(default=None, description="Most relevant clinical location.")
    attending_clinician: str | None = Field(default=None, description="Primary attending clinician.")
    reason_for_visit: str | None = Field(default=None, description="Chief complaint or reason for visit.")
    discharge_disposition: str | None = Field(
        default=None,
        description="Disposition or discharge destination if known.",
    )


class ConditionRecord(CanonicalModel):
    condition_id: str = Field(description="Condition identifier.")
    code: str | None = Field(default=None, description="Normalized clinical code when available.")
    display: str = Field(default="Unknown condition", description="Human readable condition label.")
    clinical_status: str | None = Field(default=None, description="Clinical status for the condition.")
    verification_status: str | None = Field(
        default=None,
        description="Verification status such as confirmed or provisional.",
    )
    category: str | None = Field(default=None, description="Condition category or grouping.")
    onset_datetime: datetime | None = Field(default=None, description="Condition onset time.")
    abatement_datetime: datetime | None = Field(default=None, description="Condition resolution time.")
    recorded_at: datetime | None = Field(default=None, description="Time the condition was recorded.")


class AllergyRecord(CanonicalModel):
    allergy_id: str = Field(description="Allergy or intolerance identifier.")
    code: str | None = Field(default=None, description="Normalized clinical code when available.")
    substance: str = Field(default="Unknown substance", description="Substance or allergen label.")
    reaction: str | None = Field(default=None, description="Primary documented reaction.")
    severity: str | None = Field(default=None, description="Allergy severity classification.")
    criticality: str | None = Field(default=None, description="Criticality classification.")
    clinical_status: str | None = Field(default=None, description="Clinical status for the allergy.")
    verification_status: str | None = Field(
        default=None,
        description="Verification status for the allergy record.",
    )


class MedicationRecord(CanonicalModel):
    medication_id: str = Field(description="Medication or medication request identifier.")
    code: str | None = Field(default=None, description="Normalized medication code when available.")
    display: str = Field(default="Unknown medication", description="Human readable medication label.")
    status: str = Field(default="active", description="Medication lifecycle status.")
    dosage_text: str | None = Field(default=None, description="Normalized free-text dosage instructions.")
    route: str | None = Field(default=None, description="Medication administration route.")
    frequency: str | None = Field(default=None, description="Medication administration frequency.")
    authored_on: datetime | None = Field(default=None, description="Medication authoring timestamp.")
    prescriber: str | None = Field(default=None, description="Prescribing or reconciling clinician.")


class ObservationRecord(CanonicalModel):
    observation_id: str = Field(description="Observation identifier.")
    code: str | None = Field(default=None, description="Normalized observation code.")
    display: str = Field(default="Unknown observation", description="Human readable observation name.")
    status: str = Field(default="final", description="Observation lifecycle status.")
    value_text: str | None = Field(default=None, description="Observation textual value.")
    value_numeric: float | None = Field(default=None, description="Observation numeric value.")
    unit: str | None = Field(default=None, description="Observation unit.")
    interpretation: str | None = Field(default=None, description="Observation interpretation code or label.")
    effective_at: datetime | None = Field(default=None, description="Observation effective timestamp.")


class ProvenanceRecord(CanonicalModel):
    trace_id: str = Field(description="Workflow or correlation trace identifier.")
    source_system: str = Field(default="carebridge", description="Originating source system or platform.")
    source_version: str = Field(default="R5", description="FHIR or source contract version.")
    agent_name: str = Field(default="system", description="Agent or service that produced the record.")
    recorded_at: datetime = Field(
        default_factory=utc_now,
        description="Timestamp when provenance was recorded.",
    )
    note: str | None = Field(default=None, description="Optional provenance note.")
    confidence: float | None = Field(default=None, description="Optional confidence score from 0 to 1.")


class PatientSnapshot(CanonicalModel):
    patient: PatientDemographics = Field(description="Canonical patient demographics.")
    encounter: EncounterSummary | None = Field(
        default=None,
        description="Primary encounter context for the workflow.",
    )
    conditions: list[ConditionRecord] = Field(
        default_factory=list,
        description="Canonical condition records for the patient context.",
    )
    allergies: list[AllergyRecord] = Field(
        default_factory=list,
        description="Canonical allergy or intolerance records.",
    )
    medications: list[MedicationRecord] = Field(
        default_factory=list,
        description="Canonical medication records relevant to the workflow.",
    )
    observations: list[ObservationRecord] = Field(
        default_factory=list,
        description="Canonical observations relevant to the workflow.",
    )
    provenance: list[ProvenanceRecord] = Field(
        default_factory=list,
        description="Provenance records describing how the snapshot was assembled.",
    )
    assembled_at: datetime = Field(
        default_factory=utc_now,
        description="Timestamp when the canonical snapshot was assembled.",
    )


CanonicalPatient = PatientSnapshot
