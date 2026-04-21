from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.models.canonical_patient import (
    AllergyRecord,
    EncounterSummary,
    MedicationRecord,
    ObservationRecord,
    PatientSnapshot,
    ProvenanceRecord,
)
from app.models.raw_fhir import RawFHIRResource


def generate_correlation_id() -> str:
    return str(uuid4())


class WorkflowContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, validate_assignment=True)


class WorkflowMode(str, Enum):
    ED_SUMMARY = "ed_summary"
    MED_REC = "med_rec"
    DISCHARGE_HANDOFF = "discharge_handoff"
    FULL_TRANSITION_OF_CARE = "full_transition_of_care"


class TransitionType(str, Enum):
    DISCHARGE = "discharge"
    HANDOFF = "handoff"


class WorkflowRunRequest(WorkflowContractModel):
    mode: WorkflowMode = Field(
        description="Workflow mode requested for execution.",
        validation_alias=AliasChoices("mode", "workflow"),
    )
    patient_id: str = Field(description="Patient identifier for the workflow.")
    encounter_id: str | None = Field(default=None, description="Encounter identifier for workflow context.")
    patient_snapshot: PatientSnapshot | None = Field(
        default=None,
        description="Optional canonical patient snapshot if already assembled upstream.",
        validation_alias=AliasChoices("patient_snapshot", "snapshot"),
    )
    source_resources: list[RawFHIRResource] = Field(
        default_factory=list,
        description="Raw FHIR resources available to the workflow.",
        validation_alias=AliasChoices("source_resources", "resources"),
    )
    requested_by: str | None = Field(default=None, description="Requesting user or service principal.")
    correlation_id: str = Field(
        default_factory=generate_correlation_id,
        description="End-to-end correlation identifier for this workflow run.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Stable extension bag for non-core workflow request metadata.",
    )

    def to_medrec_request(self) -> "MedRecRequest":
        snapshot = self.patient_snapshot
        return MedRecRequest(
            patient_id=self.patient_id,
            encounter_id=self.encounter_id,
            medications=list(snapshot.medications) if snapshot else [],
            allergies=list(snapshot.allergies) if snapshot else [],
            patient_snapshot=snapshot,
            source_resources=self.source_resources,
            requested_by=self.requested_by,
            correlation_id=self.correlation_id,
            metadata=self.metadata,
        )

    def to_transition_request(self) -> "TransitionRequest":
        requested_outputs = ["discharge_summary", "handoff_summary"]

        return TransitionRequest(
            mode=self.mode,
            patient_id=self.patient_id,
            encounter_id=self.encounter_id,
            patient_snapshot=self.patient_snapshot,
            source_resources=self.source_resources,
            requested_by=self.requested_by,
            correlation_id=self.correlation_id,
            metadata=self.metadata,
            requested_outputs=requested_outputs,
        )

    @property
    def workflow(self) -> WorkflowMode:
        return self.mode


class MedicationFinding(WorkflowContractModel):
    finding_id: str = Field(
        default_factory=generate_correlation_id,
        description="Identifier for the medication finding.",
    )
    category: str = Field(description="Finding category such as duplicate or allergy conflict.")
    severity: str = Field(default="info", description="Finding severity level.")
    medication_id: str | None = Field(default=None, description="Medication identifier tied to the finding.")
    medication_display: str | None = Field(default=None, description="Human readable medication name.")
    rationale: str = Field(description="Clinical or technical rationale for the finding.")
    recommended_action: str | None = Field(
        default=None,
        description="Suggested follow-up or remediation action.",
    )


class WorkflowRunResponse(WorkflowContractModel):
    status: str = Field(default="accepted", description="Execution status for the workflow request.")
    mode: WorkflowMode = Field(
        description="Workflow mode associated with the response.",
        validation_alias=AliasChoices("mode", "workflow"),
    )
    patient_id: str = Field(description="Patient identifier for the workflow.")
    encounter_id: str | None = Field(default=None, description="Encounter identifier for the workflow.")
    correlation_id: str = Field(description="End-to-end workflow correlation identifier.")
    message: str = Field(description="Human readable workflow status message.")
    summary_text: str | None = Field(default=None, description="High-level summary text when available.")
    findings: list[MedicationFinding] = Field(
        default_factory=list,
        description="Structured findings produced during workflow execution.",
    )
    patient_snapshot: PatientSnapshot | None = Field(
        default=None,
        description="Canonical snapshot returned with the workflow when available.",
        validation_alias=AliasChoices("patient_snapshot", "snapshot"),
    )
    provenance: list[ProvenanceRecord] = Field(
        default_factory=list,
        description="Provenance records attached to the workflow response.",
    )
    artifacts: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional workflow artifacts and structured outputs.",
    )

    @classmethod
    def accepted(
        cls,
        mode: WorkflowMode,
        patient_id: str,
        encounter_id: str | None,
        correlation_id: str,
        message: str,
        artifacts: dict[str, Any] | None = None,
        findings: list[MedicationFinding] | None = None,
        patient_snapshot: PatientSnapshot | None = None,
    ) -> "WorkflowRunResponse":
        return cls(
            status="accepted",
            mode=mode,
            patient_id=patient_id,
            encounter_id=encounter_id,
            correlation_id=correlation_id,
            message=message,
            findings=findings or [],
            patient_snapshot=patient_snapshot,
            artifacts=artifacts or {},
        )

    @property
    def workflow(self) -> WorkflowMode:
        return self.mode

    @property
    def trace_id(self) -> str:
        return self.correlation_id


class ContextFetchRequest(WorkflowContractModel):
    patient_id: str = Field(description="Patient identifier used for context retrieval.")
    encounter_id: str | None = Field(default=None, description="Encounter identifier used to scope context retrieval.")
    source_version: str = Field(default="R5", description="FHIR version expected from the source system.")
    include_resource_types: list[str] = Field(
        default_factory=lambda: [
            "Patient",
            "Encounter",
            "Condition",
            "AllergyIntolerance",
            "MedicationRequest",
            "Observation",
        ],
        description="Resource types requested during context retrieval.",
    )
    correlation_id: str = Field(
        default_factory=generate_correlation_id,
        description="Correlation identifier for the fetch operation.",
    )


class ContextFetchResponse(WorkflowContractModel):
    status: str = Field(default="completed", description="Status of the context fetch operation.")
    patient_id: str = Field(description="Patient identifier for the fetched context.")
    encounter_id: str | None = Field(default=None, description="Encounter identifier for the fetched context.")
    source_version: str = Field(default="R5", description="FHIR version returned from the source system.")
    raw_resource_count: int = Field(
        default=0,
        description="Count of raw FHIR resources retrieved before normalization.",
    )
    resources: list[RawFHIRResource] = Field(
        default_factory=list,
        description="Raw FHIR resources fetched for the requested context.",
    )
    patient_snapshot: PatientSnapshot | None = Field(
        default=None,
        description="Optional canonical snapshot built from the fetched resources.",
        validation_alias=AliasChoices("patient_snapshot", "snapshot"),
    )
    provenance: list[ProvenanceRecord] = Field(
        default_factory=list,
        description="Provenance metadata for the context fetch.",
    )
    message: str = Field(description="Human readable context fetch result.")


class MedRecRequest(WorkflowContractModel):
    patient_id: str = Field(description="Patient identifier for medication reconciliation.")
    encounter_id: str | None = Field(default=None, description="Encounter identifier for the reconciliation context.")
    medications: list[MedicationRecord] = Field(
        default_factory=list,
        description="Medication records considered for reconciliation.",
    )
    allergies: list[AllergyRecord] = Field(
        default_factory=list,
        description="Allergy records relevant to medication safety review.",
    )
    patient_snapshot: PatientSnapshot | None = Field(
        default=None,
        description="Canonical snapshot used to seed medication reconciliation.",
        validation_alias=AliasChoices("patient_snapshot", "snapshot"),
    )
    source_resources: list[RawFHIRResource] = Field(
        default_factory=list,
        description="Raw FHIR resources supporting medication reconciliation.",
        validation_alias=AliasChoices("source_resources", "resources"),
    )
    requested_by: str | None = Field(default=None, description="Requesting user or service principal.")
    correlation_id: str = Field(
        default_factory=generate_correlation_id,
        description="Correlation identifier for the reconciliation request.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Stable extension bag for medication reconciliation metadata.",
    )


class MedRecResponse(WorkflowContractModel):
    status: str = Field(default="accepted", description="Medication reconciliation execution status.")
    mode: WorkflowMode = Field(default=WorkflowMode.MED_REC, description="Workflow mode for this response.")
    patient_id: str = Field(description="Patient identifier for medication reconciliation.")
    encounter_id: str | None = Field(default=None, description="Encounter identifier for reconciliation context.")
    correlation_id: str = Field(description="Correlation identifier for the reconciliation workflow.")
    message: str = Field(description="Human readable reconciliation status message.")
    summary_text: str | None = Field(default=None, description="Deterministic medication reconciliation summary.")
    normalized_medications: list[MedicationRecord] = Field(
        default_factory=list,
        description="Normalized medications returned by the reconciliation workflow.",
    )
    issues: list[MedicationFinding] = Field(
        default_factory=list,
        description="Structured medication reconciliation issues.",
    )
    findings: list[MedicationFinding] = Field(
        default_factory=list,
        description="Structured medication findings identified during reconciliation.",
    )
    verification_questions: list[str] = Field(
        default_factory=list,
        description="Follow-up questions generated for human verification.",
        serialization_alias="verificationQuestions",
        validation_alias=AliasChoices("verification_questions", "verificationQuestions"),
    )
    provenance: list[ProvenanceRecord] = Field(
        default_factory=list,
        description="Provenance records generated by the medication reconciliation workflow.",
    )

    @classmethod
    def accepted(
        cls,
        patient_id: str,
        encounter_id: str | None,
        correlation_id: str,
        message: str,
        summary_text: str | None = None,
        normalized_medications: list[MedicationRecord] | None = None,
        issues: list[MedicationFinding] | None = None,
        findings: list[MedicationFinding] | None = None,
        verification_questions: list[str] | None = None,
    ) -> "MedRecResponse":
        resolved_issues = issues if issues is not None else (findings or [])
        resolved_findings = findings if findings is not None else resolved_issues
        return cls(
            status="accepted",
            patient_id=patient_id,
            encounter_id=encounter_id,
            correlation_id=correlation_id,
            message=message,
            summary_text=summary_text,
            normalized_medications=normalized_medications or [],
            issues=resolved_issues,
            findings=resolved_findings,
            verification_questions=verification_questions or [],
        )

    def to_workflow_response(self) -> WorkflowRunResponse:
        return WorkflowRunResponse(
            status=self.status,
            mode=self.mode,
            patient_id=self.patient_id,
            encounter_id=self.encounter_id,
            correlation_id=self.correlation_id,
            message=self.message,
            summary_text=self.summary_text,
            findings=self.issues or self.findings,
            artifacts={
                "normalized_medications": [med.model_dump() for med in self.normalized_medications],
                "verificationQuestions": self.verification_questions,
            },
            provenance=self.provenance,
        )

    @property
    def trace_id(self) -> str:
        return self.correlation_id


class TransitionRequest(WorkflowContractModel):
    mode: WorkflowMode = Field(
        default=WorkflowMode.DISCHARGE_HANDOFF,
        description="Transition workflow mode requested.",
        validation_alias=AliasChoices("mode", "workflow"),
    )
    patient_id: str = Field(description="Patient identifier for transition-of-care workflows.")
    encounter_id: str | None = Field(default=None, description="Encounter identifier for transition context.")
    transition_type: TransitionType = Field(
        default=TransitionType.DISCHARGE,
        description="Specific transition artifact to prepare.",
    )
    patient_snapshot: PatientSnapshot | None = Field(
        default=None,
        description="Canonical snapshot used for discharge or handoff generation.",
        validation_alias=AliasChoices("patient_snapshot", "snapshot"),
    )
    source_resources: list[RawFHIRResource] = Field(
        default_factory=list,
        description="Raw FHIR resources supporting the transition workflow.",
        validation_alias=AliasChoices("source_resources", "resources"),
    )
    requested_outputs: list[str] = Field(
        default_factory=lambda: ["discharge_summary"],
        description="Requested transition artifacts to generate.",
    )
    requested_by: str | None = Field(default=None, description="Requesting user or service principal.")
    correlation_id: str = Field(
        default_factory=generate_correlation_id,
        description="Correlation identifier for the transition request.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Stable extension bag for transition workflow metadata.",
    )


class TransitionResponse(WorkflowContractModel):
    status: str = Field(default="accepted", description="Transition workflow execution status.")
    mode: WorkflowMode = Field(
        default=WorkflowMode.DISCHARGE_HANDOFF,
        description="Workflow mode for the transition response.",
    )
    patient_id: str = Field(description="Patient identifier for the transition workflow.")
    encounter_id: str | None = Field(default=None, description="Encounter identifier for transition context.")
    correlation_id: str = Field(description="Correlation identifier for the transition workflow.")
    message: str = Field(description="Human readable transition status message.")
    summary_text: str | None = Field(default=None, description="Generated discharge or handoff summary text.")
    handoff_sections: dict[str, str] = Field(
        default_factory=dict,
        description="Structured transition summary sections keyed by section name.",
    )
    provenance: list[ProvenanceRecord] = Field(
        default_factory=list,
        description="Provenance records generated by the transition workflow.",
    )
    artifacts: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional transition workflow artifacts.",
    )

    @classmethod
    def accepted(
        cls,
        patient_id: str,
        encounter_id: str | None,
        correlation_id: str,
        message: str,
        mode: WorkflowMode = WorkflowMode.DISCHARGE_HANDOFF,
        summary_text: str | None = None,
        artifacts: dict[str, Any] | None = None,
    ) -> "TransitionResponse":
        return cls(
            status="accepted",
            mode=mode,
            patient_id=patient_id,
            encounter_id=encounter_id,
            correlation_id=correlation_id,
            message=message,
            summary_text=summary_text,
            artifacts=artifacts or {},
        )

    def to_workflow_response(self) -> WorkflowRunResponse:
        return WorkflowRunResponse(
            status=self.status,
            mode=self.mode,
            patient_id=self.patient_id,
            encounter_id=self.encounter_id,
            correlation_id=self.correlation_id,
            message=self.message,
            summary_text=self.summary_text,
            provenance=self.provenance,
            artifacts={
                "handoff_sections": self.handoff_sections,
                **self.artifacts,
            },
        )

    @property
    def workflow(self) -> WorkflowMode:
        return self.mode

    @property
    def trace_id(self) -> str:
        return self.correlation_id


WorkflowType = WorkflowMode
EncounterContext = EncounterSummary
MedicationItem = MedicationRecord
ObservationItem = ObservationRecord
MedRecRunRequest = MedRecRequest
MedRecRunResponse = MedRecResponse
TransitionRunRequest = TransitionRequest
TransitionRunResponse = TransitionResponse
