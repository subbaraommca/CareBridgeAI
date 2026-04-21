from contextlib import contextmanager

from app.config.settings import Settings
from app.models.raw_fhir import RawFHIRResource
from app.models.workflow_models import WorkflowMode
from app.persistence.postgres import PostgresConfig
from app.persistence.repositories import (
    AgentOutputRecord,
    AgentOutputRepository,
    RawFHIRResourceRecord,
    RawFHIRResourceRepository,
    WorkflowRunRecord,
    WorkflowRunRepository,
)
from app.services.audit.audit_logger import AuditLogger, AuditStepStatus
from app.services.audit.provenance import build_provenance_envelope


class FakeCursor:
    def __init__(self, connection: "FakeConnection") -> None:
        self.connection = connection

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def execute(self, query: str, params: dict | None = None) -> None:
        self.connection.executed.append((query, params or {}))

    def fetchall(self) -> list[dict]:
        return list(self.connection.fetchall_result)

    def fetchone(self) -> dict | None:
        return self.connection.fetchone_result


class FakeConnection:
    def __init__(self) -> None:
        self.executed: list[tuple[str, dict]] = []
        self.fetchall_result: list[dict] = []
        self.fetchone_result: dict | None = None
        self.commits = 0
        self.closed = False

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)

    def commit(self) -> None:
        self.commits += 1

    def close(self) -> None:
        self.closed = True


class FakeConnectionFactory:
    def __init__(self, connection: FakeConnection | None = None) -> None:
        self.connection_instance = connection or FakeConnection()

    @contextmanager
    def connection(self):
        yield self.connection_instance


def test_postgres_config_builds_from_settings() -> None:
    config = PostgresConfig.from_settings(
        Settings(postgres_dsn="postgresql://carebridge:secret@localhost:5432/carebridge")
    )

    assert config.dsn == "postgresql://carebridge:secret@localhost:5432/carebridge"
    assert config.application_name == "carebridge-backend"


def test_workflow_run_repository_saves_minimal_record() -> None:
    factory = FakeConnectionFactory()
    repository = WorkflowRunRepository(connection_factory=factory)
    record = WorkflowRunRecord(
        trace_id="trace-1",
        workflow_mode=WorkflowMode.MED_REC,
        patient_id="patient-123",
        source_version="R4",
        status="completed",
        request_payload={"patient_id": "patient-123"},
        response_payload={"status": "completed"},
    )

    saved = repository.save(record)

    query, params = factory.connection_instance.executed[0]
    assert saved == record
    assert "INSERT INTO workflow_runs" in query
    assert params["trace_id"] == "trace-1"
    assert params["workflow_mode"] == WorkflowMode.MED_REC.value
    assert factory.connection_instance.commits == 1


def test_agent_output_repository_saves_structured_payload() -> None:
    factory = FakeConnectionFactory()
    repository = AgentOutputRepository(connection_factory=factory)
    record = AgentOutputRecord(
        trace_id="trace-2",
        workflow_mode=WorkflowMode.ED_SUMMARY,
        agent_name="ed-summary-agent",
        output_type="summary",
        payload={"summary_text": "Example summary"},
    )

    repository.save(record)

    query, params = factory.connection_instance.executed[0]
    assert "INSERT INTO agent_outputs" in query
    assert params["agent_name"] == "ed-summary-agent"
    assert params["workflow_mode"] == WorkflowMode.ED_SUMMARY.value


def test_raw_fhir_resource_repository_builds_record_from_wrapper() -> None:
    resource = RawFHIRResource(
        source_version="R4",
        resource_type="Patient",
        resource_id="patient-123",
        payload={"resourceType": "Patient", "id": "patient-123"},
    )
    record = RawFHIRResourceRecord.from_raw_resource(
        trace_id="trace-3",
        patient_id="patient-123",
        resource=resource,
    )
    factory = FakeConnectionFactory()
    repository = RawFHIRResourceRepository(connection_factory=factory)

    repository.save(record)

    query, params = factory.connection_instance.executed[0]
    assert "INSERT INTO raw_fhir_resources" in query
    assert params["resource_type"] == "Patient"
    assert params["resource_id"] == "patient-123"


def test_audit_logger_records_structured_step_metadata() -> None:
    sink = []
    logger = AuditLogger(event_sink=sink)

    event = logger.record_step(
        trace_id="trace-4",
        workflow_mode=WorkflowMode.FULL_TRANSITION_OF_CARE,
        source_version="R4",
        step_name="patient-context-fetch",
        step_status=AuditStepStatus.COMPLETED,
        details={"raw_resource_count": 7},
    )

    assert event.trace_id == "trace-4"
    assert event.workflow_mode is WorkflowMode.FULL_TRANSITION_OF_CARE
    assert event.source_version == "R4"
    assert event.step_status is AuditStepStatus.COMPLETED
    assert sink == [event]


def test_build_provenance_envelope_includes_source_normalization_and_summarization() -> None:
    envelope = build_provenance_envelope(
        trace_id="trace-5",
        source_system="epic-sandbox",
        source_version="R4",
        normalization_version="normalize-v2",
        summarization_version="summary-v3",
        summarization_model="gemini-2.0-flash",
        used_fallback=True,
    )

    assert envelope.trace_id == "trace-5"
    assert envelope.source.source_system == "epic-sandbox"
    assert envelope.source.source_version == "R4"
    assert envelope.normalization.normalization_version == "normalize-v2"
    assert envelope.summarization is not None
    assert envelope.summarization.summarization_version == "summary-v3"
    assert envelope.summarization.used_fallback is True
