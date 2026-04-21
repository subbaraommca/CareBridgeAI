import logging

from fastapi import APIRouter, HTTPException, status

from app.models.canonical_patient import ProvenanceRecord
from app.models.raw_fhir import RawFHIRResource
from app.models.workflow_models import ContextFetchRequest, ContextFetchResponse

router = APIRouter(prefix="/api/context", tags=["context"])
logger = logging.getLogger(__name__)


def build_context_placeholder_response(payload: ContextFetchRequest) -> ContextFetchResponse:
    if not payload.patient_id.strip():
        raise ValueError("patient_id must not be empty.")

    resources = [
        RawFHIRResource(
            source_version=payload.source_version,
            resource_type=resource_type,
            resource_id=(
                payload.patient_id
                if resource_type == "Patient"
                else payload.encounter_id or f"{payload.patient_id}-{resource_type.lower()}"
            ),
            payload={
                "resourceType": resource_type,
                "id": (
                    payload.patient_id
                    if resource_type == "Patient"
                    else payload.encounter_id or f"{payload.patient_id}-{resource_type.lower()}"
                ),
                "subject": {"reference": f"Patient/{payload.patient_id}"},
            },
        )
        for resource_type in payload.include_resource_types
    ]

    return ContextFetchResponse(
        status="completed",
        patient_id=payload.patient_id,
        encounter_id=payload.encounter_id,
        source_version=payload.source_version,
        resources=resources,
        provenance=[
            ProvenanceRecord(
                trace_id=payload.correlation_id,
                agent_name="context-route",
                note="Placeholder context bundle synthesized from request parameters.",
            )
        ],
        message="Context fetch placeholder completed successfully.",
    )


@router.post("/fetch", response_model=ContextFetchResponse, status_code=status.HTTP_200_OK)
async def fetch_context(payload: ContextFetchRequest) -> ContextFetchResponse:
    try:
        return build_context_placeholder_response(payload)
    except ValueError as exc:
        logger.warning("Invalid context fetch request: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected context route failure")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to fetch context.",
        ) from exc
