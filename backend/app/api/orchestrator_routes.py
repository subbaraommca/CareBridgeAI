import logging

from fastapi import APIRouter, HTTPException, status

from app.agents.orchestrator_agent import OrchestratorAgent
from app.models.workflow_models import WorkflowRunRequest, WorkflowRunResponse

router = APIRouter(prefix="/api/workflow", tags=["workflow"])
logger = logging.getLogger(__name__)
orchestrator_agent = OrchestratorAgent()


@router.post("/run", response_model=WorkflowRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def run_workflow(payload: WorkflowRunRequest) -> WorkflowRunResponse:
    try:
        return orchestrator_agent.run(payload)
    except ValueError as exc:
        logger.warning("Invalid workflow request: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected workflow route failure")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to process workflow request.",
        ) from exc
